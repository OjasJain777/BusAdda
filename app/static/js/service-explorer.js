import { button, el, stopName, svg } from "./ui.js";

export function serviceExplorer(network, onToggle, onVisibility, onClear) {
  const search = document.querySelector("#directory-search");
  const list = document.querySelector("#directory");
  const visibility = document.querySelector("#route-visibility");
  const clear = document.querySelector("#clear-services");
  const cards = new Map();

  for (const service of network.services) {
    const direction = service.directions[0] || Object.values(service.directions)[0];
    const card = button("", "directory-item service-item");
    card.setAttribute("aria-pressed", "false");
    const header = el("span", "service-heading");
    const dot = svg("svg", { viewBox: "0 0 14 14", width: 14, height: 14, "aria-hidden": "true" });
    dot.append(svg("circle", { cx: 7, cy: 7, r: 5, fill: service.color }));
    header.append(dot, el("strong", null, "Bus " + service.number));
    card.append(header, el("span", null, service.name), el("small", null, direction.stops.length + " stops"));
    card.addEventListener("click", () => onToggle(service.id));
    cards.set(service.id, { card, text: (service.number + " " + service.name).toLowerCase() });
    list.append(card);
  }
  const empty = el("p", "muted", "No routes match this search.");
  empty.hidden = true;
  list.append(empty);

  search.addEventListener("input", () => {
    const query = search.value.trim().toLowerCase();
    let count = 0;
    for (const { card, text } of cards.values()) {
      card.hidden = !text.includes(query);
      if (!card.hidden) count++;
    }
    empty.hidden = count > 0;
  });
  visibility.addEventListener("change", () => onVisibility(visibility.value));
  clear.addEventListener("click", onClear);

  return (selected, mode) => {
    visibility.value = mode;
    clear.disabled = !selected.size;
    cards.forEach(({ card }, id) => card.setAttribute("aria-pressed", String(selected.has(id))));
  };
}

export function serviceDetails(container, network, service, onStop) {
  const direction = service.directions[0] || Object.values(service.directions)[0];
  const count = network.vehicles.filter((vehicle) => vehicle.service === service.id).length;
  container.append(
    el("p", "service-title", service.name),
    el("p", null, direction.stops.length + " stops · " + direction.km + " km · ~" + direction.minutes + " min"),
    el("p", null, count + (count === 1 ? " simulated bus" : " simulated buses")),
  );
  const expanded = el("details", "service-stops");
  expanded.append(el("summary", null, "Stops in order"));
  const stops = el("ol");
  for (const id of direction.stops) {
    const item = el("li");
    const control = button(stopName(network, id), "service-stop-button");
    control.addEventListener("click", () => onStop(id));
    item.append(control);
    stops.append(item);
  }
  expanded.append(stops);
  container.append(expanded);
}
