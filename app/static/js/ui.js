const svgNamespace = "http://www.w3.org/2000/svg";

export function svg(tag, attrs = {}) {
  const node = document.createElementNS(svgNamespace, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  return node;
}

export function icon(name, size = 18) {
  const node = svg("svg", {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
    "stroke-width": "1.65", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true",
  });
  node.append(svg("use", { href: "/static/icons.svg#" + name }));
  return node;
}

export function el(tag, classes, content) {
  const node = document.createElement(tag);
  if (classes) node.className = classes;
  if (content != null) node.textContent = content;
  return node;
}

export function button(text, classes, glyph) {
  const node = el("button", classes);
  node.type = "button";
  if (glyph) node.append(icon(glyph, 15));
  node.append(document.createTextNode(text));
  return node;
}

export async function api(path, method = "GET", body) {
  const response = await fetch("/api/" + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": document.querySelector('[name="csrf-token"]').content,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "BusAdda could not complete this request.");
  return data;
}

let toastTimer;
export function notify(message) {
  const node = document.querySelector("#toast");
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 4000);
}

export function stopName(network, id) {
  return network.byStop.get(id)?.name ?? "Unavailable stop";
}
