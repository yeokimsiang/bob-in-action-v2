// The recorded desk's only addition to the app: it answers the app's own fetch calls from the answers
// the real app gave when it was recorded (recording.js), and never touches the network. A call that was
// not recorded gets a plain note instead, shown in the app's own message line and beside the desk.
// Keys are built exactly as the recorder built them.
(function () {
  "use strict";
  var R = window.DESK_RECORDING;
  var state = R.start;
  var NOTE = "This copy has the real app's answers for the recorded orders. " +
    "Use Try this order, type an order in as the steps beside the desk say, or start the real app yourself (Start it).";

  function canonical(value) {
    if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
    if (value && typeof value === "object") {
      return "{" + Object.keys(value).sort().map(function (name) {
        return JSON.stringify(name) + ":" + canonical(value[name]);
      }).join(",") + "}";
    }
    return JSON.stringify(value);
  }

  function keyOf(url, options) {
    var method = ((options && options.method) || "GET").toUpperCase();
    var parsed = new URL(url, "http://desk.invalid");
    if (method === "GET") {
      var params = [];
      parsed.searchParams.forEach(function (value, name) {
        params.push(name + "=" + (name === "q" ? value.toLowerCase() : value));
      });
      return "GET " + parsed.pathname + (params.length ? "?" + params.join("&") : "");
    }
    var body;
    try { body = JSON.parse((options && options.body) || "null"); } catch (error) { body = options.body; }
    return method + " " + parsed.pathname + " " + canonical(body);
  }

  // A state lists only the answers that differ from the sample data's; the recorder checked that every
  // state answered every request the sample data did.
  function answer(key) {
    var here = R.states[state];
    var move = here.moves[key];
    if (move) {
      state = move.to;
      return R.answers[move.answer];
    }
    var number = key in here.answers ? here.answers[key] : R.states[R.start].answers[key];
    return number === undefined ? null : R.answers[number];
  }

  function tell(message, text) {
    if (window.parent !== window) window.parent.postMessage({ source: "legacy-desk", type: message, text: text || "" }, "*");
  }

  window.fetch = function (url, options) {
    var key = keyOf(url, options);
    var found = answer(key);
    if (!found) {
      tell("not-recorded");
      return Promise.resolve(new Response(JSON.stringify({ message: NOTE }), {
        status: 404, headers: { "Content-Type": "application/json" }
      }));
    }
    // A preview, save, request or job: the page says whether the real app refused it too, and in what words.
    if (key.indexOf("GET ") !== 0) {
      if (found.status >= 400) tell("refused", found.body && found.body.message);
      else tell("answered");
    }
    var text = "body" in found ? JSON.stringify(found.body) : found.text;
    return Promise.resolve(new Response(text, { status: found.status, headers: { "Content-Type": "application/json" } }));
  };

  // Numbered marks matching the notes beside the desk; ours, not the app's.
  var MARKS = [["customer-search", 1], ["preview-invoice", 2], ["save-invoice", 3], ["invoice-search", 4],
    ["create-credit-request", 5], ["run-invoice-job", 6], ["monthly-report", 7]];
  function mark() {
    var style = document.createElement("style");
    // align-self: the app's labels are flex columns, which would stretch the mark across the field.
    style.textContent = ".rec-mark{display:inline-block;align-self:flex-start;min-width:22px;height:22px;margin:0 6px 0 0;padding:0 4px;" +
      "background:#0076D3;color:#FFFFFF;font:700 13px/22px Arial,sans-serif;text-align:center;vertical-align:middle}";
    document.head.appendChild(style);
    MARKS.forEach(function (pair) {
      var target = document.getElementById(pair[0]);
      if (!target) return;
      var badge = document.createElement("span");
      badge.className = "rec-mark";
      badge.setAttribute("aria-hidden", "true");
      badge.textContent = String(pair[1]);
      // Inside the label or button, so the app's own grid keeps its cells.
      var place = target.closest("label") || target;
      place.insertBefore(badge, place.firstChild);
    });
  }

  // "Try this order": the page reloads the desk with ?try=<order> (a fresh start each time) and the shim
  // fills the form with the app's own controls once the app has loaded its customers and products.
  // Nothing is sent until the visitor presses a button.
  function whenReady(then) {
    var tries = 0;
    (function wait() {
      var products = document.getElementById("product-select");
      var customers = document.getElementById("customer-select");
      if (products && products.options.length && customers && customers.options.length) return then();
      if (++tries < 200) setTimeout(wait, 25);
    })();
  }

  // Scrolls the desk's own window only; scrollIntoView would also move the page around it.
  function show(id) {
    var top = document.getElementById(id).getBoundingClientRect().top + window.pageYOffset;
    window.scrollTo(0, Math.max(0, top - 8));
  }

  function fill(name) {
    var order = R.orders.filter(function (item) { return item.id === name; })[0];
    var $ = function (id) { return document.getElementById(id); };
    if (order) {
      $("customer-select").value = String(order.customerId);
      order.lines.forEach(function (line) {
        $("product-select").value = line[0];
        $("product-select").dispatchEvent(new Event("change"));
        $("quantity-input").value = String(line[1]);
        $("add-line").click();
      });
      show("prepare");
      $("preview-invoice").focus({ preventScroll: true });
    } else if (name === "credit") {
      $("credit-invoice").value = String(R.credit.invoiceId);
      $("credit-amount").value = R.credit.amountNet;
      $("credit-reason").value = R.credit.reason;
      show("credits");
      $("create-credit-request").focus({ preventScroll: true });
    } else {
      return;
    }
    tell("filled");
  }

  document.addEventListener("DOMContentLoaded", function () {
    mark();
    var wanted = new URLSearchParams(window.location.search).get("try");
    if (wanted && /^[a-z]+$/.test(wanted)) whenReady(function () { fill(wanted); });
  });
})();
