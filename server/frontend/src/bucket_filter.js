/*
 * Parsing is delegated to the  `liqe` library, which understands
 *  `key:value`, AND/OR/NOT, parentheses, and NOT negation.
 * `queryStrToServerQuery` walks liqe's AST and forms JSON Q-object
 * via each filter key's `toQuery`.
 *
 * Autocomplete (buildSuggestions / acceptSuggestion) is independent
 * of the parser and uses lightweight string analysis of the caret fragment.
 *
 * Grammar accepted:
 *   - term:        `key:value` (keys: domain, country);
 *   - operators:   AND, OR, NOT;
 *   - adjacent terms: adds implicit AND;
 *   - grouping:    parentheses.
 *
 * NOTE on precedence: liqe binds AND/OR left-to-right at equal precedence, so
 * an un-parenthesized mixed query like `a OR b AND c` means `(a OR b) AND c`,
 * NOT the conventional `a OR (b AND c)`. Parenthesize mixed queries to be
 * explicit; pure-AND, pure-OR, and parenthesized queries are unambiguous.
 */
import { parse } from "liqe";

export const BUCKET_STATES = {
  all: { label: "All", queryFields: () => ({}) },
  needs_triage: {
    label: "Needs Triage",
    queryFields: () => ({ bug__isnull: true, triage_status__isnull: true }),
  },
  has_bug: {
    label: "Has a bug",
    queryFields: () => ({ bug__isnull: false }),
  },
  triaged: {
    label: "Triaged",
    queryFields: ({ triageStatus }) =>
      triageStatus
        ? { triage_status: triageStatus }
        : { triage_status__isnull: false },
  },
};

export const BUCKET_FILTERS = {
  country: {
    key: "country",
    label: "Country",
    suggest: (fragment, options) => {
      const q = fragment.toLowerCase();
      return (options.countries ?? [])
        .filter(
          (c) =>
            c.code.toLowerCase().includes(q) ||
            c.name.toLowerCase().includes(q),
        )
        .map((c) => ({
          value: c.code,
          display: c.name,
          badge: c.code,
          key: "country",
        }));
    },
    toQuery: (value) => ({ op: "AND", reportentry__country: value }),
  },
  label: {
    key: "label",
    label: "Label",
    suggest: (fragment, options) => {
      const q = fragment.toLowerCase();
      return (options.labels ?? [])
        .filter((l) => l.name.toLowerCase().includes(q))
        .map((l) => ({ value: l.name, display: l.name, key: "label" }));
    },
    toQuery: (value) => ({ op: "AND", labels__label__name: value }),
  },
  domain: {
    key: "domain",
    label: "Domain",
    suggest: (fragment) =>
      fragment
        ? [{ value: fragment, display: `domain: ${fragment}`, key: "domain" }]
        : [],
    toQuery: (value) => ({
      op: "OR",
      domain: value,
      domain__endswith: `.${value}`,
    }),
  },
};

const OPS = ["AND", "OR", "NOT"];

// Walk a liqe AST node into our backend Q-object, returning
// { result, error }: at most one is non-null.
//   - result non-null, error null  -> the node mapped to a Q-object
//   - result null, error null      -> the node legitimately contributes
//                                     nothing (empty expression)
//   - result null, error non-null  -> the node can't be turned into a real
//                                     query; `error` is a user-facing message
// An unknown field, a bare free-text term, or any node type we
// don't understand is an error rather than being silently dropped, so the user
// never gets results that don't reflect what they typed.
//
// liqe node types: Tag (field:value), LogicalExpression (left/right + boolean
// operator), UnaryOperator ('-'|'NOT'), ParenthesizedExpression,
// EmptyExpression, LiteralExpression (bare free text).
const ok = (result) => ({ result, error: null });
const empty = { result: null, error: null };
const fail = (error) => ({ result: null, error });

const nodeToQuery = (node) => {
  if (!node) {
    return empty;
  }
  switch (node.type) {
    case "EmptyExpression":
      return empty;
    case "ParenthesizedExpression":
      return nodeToQuery(node.expression);
    case "Tag": {
      if (
        node.field?.type !== "Field" ||
        node.expression?.value === undefined
      ) {
        return fail(
          "Free-text search isn't supported yet. Use field:value without a space in between, e.g. domain:example.com.",
        );
      }
      // We only support equality (`field:value`) for now. liqe also parses comparison
      // operators (`field:>=10`, `field:<5`, …); reject them.
      if (node.operator?.operator !== ":") {
        return fail(
          `Unsupported operator "${node.operator?.operator}". Only field:value is supported.`,
        );
      }
      const key = node.field.name.toLowerCase();
      const def = BUCKET_FILTERS[key];
      if (!def) {
        return fail(`Unknown field "${node.field.name}".`);
      }
      return ok(def.toQuery(node.expression.value));
    }
    case "UnaryOperator": {
      // both '-' and 'NOT' negate the operand
      const inner = nodeToQuery(node.operand);
      if (inner.error) {
        return inner;
      }
      return inner.result ? ok({ op: "NOT", 0: inner.result }) : empty;
    }
    case "LogicalExpression": {
      const op = node.operator.operator;
      const left = nodeToQuery(node.left);
      const right = nodeToQuery(node.right);
      const childError = left.error ?? right.error;
      if (childError) {
        return fail(childError);
      }
      const children = [left.result, right.result].filter(Boolean);
      if (!children.length) {
        return empty;
      }
      if (children.length === 1) {
        return ok(children[0]);
      }
      const out = { op };
      children.forEach((child, i) => {
        out[i] = child;
      });
      return ok(out);
    }
    default:
      return fail("Unsupported query.");
  }
};

// Convert a query string to the backend Q-object, returning { result, error }
// (see nodeToQuery). An empty/whitespace query is { result: null, error: null }.
// liqe throws a SyntaxError on malformed input (unbalanced parens, dangling
// operators); we surface that as an error too. Parsing runs only on submit.
export const queryStrToServerQuery = (str) => {
  if (!str || !str.trim()) {
    return empty;
  }
  let ast;
  try {
    ast = parse(str);
  } catch (e) {
    // liqe's parser messages are cryptic for end users; log the detail for
    // debugging and surface a friendlier message.
    console.debug("query parse error:", e);
    return fail(
      "Invalid query. Check for unbalanced parentheses or operators.",
    );
  }
  return nodeToQuery(ast);
};

// autocomplete menu from the caret fragment
const needConnector = (before) => {
  const t = before.replace(/\s+$/, "");
  if (!t || t.endsWith("(")) {
    return false;
  }
  const lastWord = (t.match(/[\w:.-]+$/) || [""])[0].toUpperCase();

  return !OPS.includes(lastWord);
};

// The "fragment" is the word the caret sits in: the run of non-space,
// non-paren characters immediately to the left of the caret. Every suggestion
// decision below is made from this fragment.
const fragmentAt = (str, caret) =>
  (str.slice(0, caret).match(/[^\s()]*$/) || [""])[0];

// True when the caret sits in the *interior* of a token, i.e. a word character
// is immediately to its right. fragmentAt only looks left, so editing the
// middle/start of an existing term (e.g. caret before "nsfw" in "label:nsfw")
// would otherwise suggest a completion the right-hand text already provides —
// accepting it would duplicate text. We suppress suggestions in that case.
const caretMidToken = (str, caret) => /[^\s()]/.test(str.charAt(caret));

// --- the three suggestion modes ---
// Each returns an array of { name, opts } groups (possibly empty).

// Mode 1: fragment is "key:partial" — complete a value for that one filter.
const valueSuggestions = (frag, options) => {
  const ci = frag.indexOf(":");
  const key = frag.slice(0, ci).toLowerCase();
  const def = BUCKET_FILTERS[key];
  if (!def) {
    return []; // unknown key — nothing to suggest
  }
  const valPart = frag.slice(ci + 1);
  return [
    {
      name: def.label,
      opts: def.suggest(valPart, options).map((s) => ({ ...s, bare: false })),
    },
  ];
};

// Mode 2: bare word (no colon) — search values across every filter. Tagged
// `bare: true` so acceptSuggestion knows to prepend an AND connector when one
// is needed.
const bareSuggestions = (frag, options) =>
  Object.values(BUCKET_FILTERS).map((def) => ({
    name: def.label,
    opts: def.suggest(frag, options).map((s) => ({ ...s, bare: true })),
  }));

// Mode 3: AND/OR/NOT, narrowed to what the user has typed so far.
const operatorSuggestions = (frag) => {
  const q = frag.toLowerCase();
  return [
    {
      name: "Operators",
      opts: OPS.filter((o) => !q || o.toLowerCase().startsWith(q)).map((o) => ({
        type: "op",
        insert: `${o} `,
        display: o,
      })),
    },
  ];
};

// Returns { groups:[{name,opts}], items:[...flat], fragStart, frag, needsConnector }
export const buildSuggestions = (str, caret, options = {}) => {
  const frag = fragmentAt(str, caret);
  const fragStart = caret - frag.length;
  const groups = [];
  const items = [];
  const addGroup = ({ name, opts }) => {
    if (!opts.length) {
      return;
    }
    opts.forEach((it) => {
      it.idx = items.length;
      items.push(it);
    });
    groups.push({ name, opts });
  };

  // When the caret sits in the interior of an existing term, the text to its
  // right already completes it — there's nothing to suggest, so we leave
  // groups/items empty (closing the dropdown) and fall through to the return.
  if (!caretMidToken(str, caret)) {
    if (frag.includes(":")) {
      // completing a value for an explicit key:partial
      valueSuggestions(frag, options).forEach(addGroup);
    } else {
      // operators only make sense once a term precedes the fragment
      const hasPrecedingTerm = Boolean(str.slice(0, fragStart).trim());
      // When the fragment looks like the start of an operator (e.g. "O", "AN"),
      // the user is reaching for AND/OR/NOT — show operators only, not key
      // values like "domain: OR".
      const looksLikeOp =
        hasPrecedingTerm &&
        frag !== "" &&
        OPS.some((o) => o.toLowerCase().startsWith(frag.toLowerCase()));

      if (!looksLikeOp) {
        bareSuggestions(frag, options).forEach(addGroup);
      }
      if (hasPrecedingTerm) {
        operatorSuggestions(frag).forEach(addGroup);
      }
    }
  }
  // The fragment is "complete" when it already equals a value suggestion's
  // key:value (e.g. "country:GB" with GB suggested) — accepting it would just
  // re-insert the same term, so Enter should submit the query instead.
  const exactMatch = items.some(
    (it) => it.type !== "op" && frag === `${it.key}:${it.value}`,
  );

  return {
    groups,
    items,
    fragStart,
    frag,
    exactMatch,
    // Connector depends on the text BEFORE the fragment being completed, not on
    // the fragment itself — typing "g" to filter the country list must not be
    // treated as a preceding term that needs an "AND".
    needsConnector: needConnector(str.slice(0, fragStart)),
  };
};

// Compute the new query string + caret after accepting a suggestion.
// Returns { queryStr, caret }.
export const acceptSuggestion = (str, caret, menu, sug) => {
  const head = str.slice(0, menu.fragStart);
  const after = str.slice(caret);
  const connector = sug.bare && menu.needsConnector ? "AND " : "";
  const insert = sug.type === "op" ? sug.insert : `${sug.key}:${sug.value} `;
  const newHead = head + connector + insert;
  return { queryStr: newHead + after, caret: newHead.length };
};

/*
 * Build the backend JSON query by AND-combining contributions:
 *   1. state (BUCKET_STATES[activeState].queryFields)
 *   2. the typed query (queryStr -> queryStrToServerQuery)
 *   and triage status is already folded into (1) for the triaged tab.
 */
export const buildQuery = ({ activeState, queryStr, triageStatus }) => {
  const state = BUCKET_STATES[activeState] ?? BUCKET_STATES.all;
  const stateQuery = { op: "AND", ...state.queryFields({ triageStatus }) };

  const { result: typed } = queryStrToServerQuery(queryStr);
  if (!typed) {
    return JSON.stringify(stateQuery, null, 2);
  }

  return JSON.stringify({ op: "AND", 0: stateQuery, 1: typed }, null, 2);
};

/*
 * Serialize the bucket list's filter state into a URL hash fragment, e.g.
 * Parsing back is done with the generic parseHash() in helpers.js.
 */
export const buildBucketHash = ({
  activeState,
  queryStr,
  triageStatus,
  currentPage,
  sort,
}) => {
  const parts = [];
  if (activeState !== "needs_triage") {
    parts.push(`state=${activeState}`);
  }
  if (triageStatus) {
    parts.push(`triage_status=${triageStatus}`);
  }
  if (queryStr && queryStr.trim()) {
    parts.push(`q=${encodeURIComponent(queryStr)}`);
  }
  if (currentPage !== 1) {
    parts.push(`page=${currentPage}`);
  }
  if (sort) {
    parts.push(`sort=${sort}`);
  }
  return parts.length ? `#${parts.join("&")}` : "";
};
