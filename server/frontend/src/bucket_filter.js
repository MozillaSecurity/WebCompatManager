/*
 * Parsing is delegated to the  `liqe` library, which understands
 *  `key:value`, AND/OR/NOT, parentheses, and NOT negation.
 * `queryStrToJson` walks liqe's AST and forms JSON Q-object
 * via each filter key's `toQuery`.
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
    toQuery: (value) => ({ op: "AND", reportentry__country: value }),
  },
  label: {
    key: "label",
    label: "Label",
    toQuery: (value) => ({ op: "AND", labels__label__name: value }),
  },
  domain: {
    key: "domain",
    label: "Domain",
    toQuery: (value) => ({
      op: "OR",
      domain: value,
      domain__endswith: `.${value}`,
    }),
  },
};

// validation: block fetch when the query can't be parsed
// liqe throws a SyntaxError on malformed input (unbalanced parens, dangling
// operators, etc.). Parsing runs only on submit, so a throw here is fine.
// Returns { valid: boolean, error: string }.
export const validateQL = (str) => {
  if (!str || !str.trim()) {
    return { valid: true, error: "" };
  }
  try {
    parse(str);
    return { valid: true, error: "" };
  } catch (e) {
    // liqe's parser messages are cryptic for end users; log the detail for
    // debugging and surface a different message.
    console.debug("query parse error:", e);
    return {
      valid: false,
      error: "Invalid query. Check for unbalanced parentheses or operators.",
    };
  }
};

// serializer: liqe AST -> backend JSON Q-object
const toQueryForKey = (key, value) => {
  const def = BUCKET_FILTERS[key];
  return def ? def.toQuery(value) : null; // unknown key ignored
};

// Walk a liqe AST node into our backend Q-object (or null if it contributes
// nothing). liqe node types: Tag (field:value), LogicalExpression (left/right +
// boolean operator), UnaryOperator ('-'|'NOT'), ParenthesizedExpression,
// EmptyExpression, LiteralExpression (bare free text — ignored, lenient).
const nodeToQuery = (node) => {
  if (!node) {
    return null;
  }
  switch (node.type) {
    case "ParenthesizedExpression":
      return nodeToQuery(node.expression);
    case "Tag": {
      // Only `field:value` tags map to a query; bare literals are ignored.
      if (
        node.field?.type !== "Field" ||
        node.expression?.value === undefined
      ) {
        return null;
      }
      const key = String(node.field.name).toLowerCase();
      return toQueryForKey(key, String(node.expression.value));
    }
    case "UnaryOperator": {
      // both '-' and 'NOT' negate the operand
      const inner = nodeToQuery(node.operand);
      return inner ? { op: "NOT", 0: inner } : null;
    }
    case "LogicalExpression": {
      const op = node.operator?.operator === "OR" ? "OR" : "AND";
      const children = [nodeToQuery(node.left), nodeToQuery(node.right)].filter(
        Boolean,
      );
      if (!children.length) {
        return null;
      }
      if (children.length === 1) {
        return children[0];
      }
      const out = { op };
      children.forEach((child, i) => {
        out[i] = child;
      });
      return out;
    }
    default:
      return null;
  }
};

export const queryStrToJson = (str) => {
  if (!str || !str.trim()) {
    return null;
  }
  let ast;
  try {
    ast = parse(str);
  } catch {
    return null; // malformed; validateQL surfaces the user-facing error
  }
  return nodeToQuery(ast);
};

/*
 * Build the backend JSON query by AND-combining contributions:
 *   1. state (BUCKET_STATES[activeState].queryFields)
 *   2. the typed query (queryStr -> queryStrToJson)
 *   and triage status is already folded into (1) for the triaged tab.
 */
export const buildQuery = ({ activeState, queryStr, triageStatus }) => {
  const state = BUCKET_STATES[activeState] ?? BUCKET_STATES.all;
  const stateQuery = { op: "AND", ...state.queryFields({ triageStatus }) };

  const typed = queryStrToJson(queryStr);
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
