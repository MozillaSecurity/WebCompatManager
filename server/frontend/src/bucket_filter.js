/*
 * Parsing is delegated to the  `liqe` library, which understands
 *  `key:value`, AND/OR/NOT, parentheses, and NOT negation.
 * `queryStrToServerQuery` walks liqe's AST and forms JSON Q-object
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
import { BUCKET_FILTERS, BUCKET_STATES } from "./bucket_filter_config";

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
      // liqe parses comparison operators as composite operator strings like
      // ":<", ":<=", ":>", ":>=". Allow them for filters that opt in via
      // supportsComparison; reject them for everything else.
      const op = node.operator?.operator;
      const isComparison = op !== ":";
      if (isComparison && op !== ":<" && op !== ":<=" && op !== ":>" && op !== ":>=") {
        return fail(
          `Unsupported operator "${op}". Only field:value is supported.`,
        );
      }
      const key = node.field.name.toLowerCase();
      const def = BUCKET_FILTERS[key];
      if (!def) {
        return fail(`Unknown field "${node.field.name}".`);
      }
      if (isComparison && !def.supportsComparison) {
        return fail(
          `Comparison operators are not supported for field "${node.field.name}".`,
        );
      }
      // Strip the leading ":" so toQuery receives "", "<", "<=", ">", ">="
      return ok(def.toQuery(node.expression.value, op.slice(1)));
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
