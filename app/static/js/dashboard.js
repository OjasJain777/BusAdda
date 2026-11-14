import { api, button, el, icon, notify, stopName, svg } from "./ui.js";
import { TransitMap } from "./map.js";
import { BusSimulation } from "./bus-animation.js";
import { corridorPath, projectSegment } from "./route-geometry.js";
import { serviceDetails, serviceExplorer } from "./service-explorer.js";
import { modeNames, RoutePlanner, routeURL } from "./route-planner.js";

const main = document.querySelector("main[data-view]");
const view = main.dataset.view;


async function readNetwork() {
  const data = await api("network");
  data.byStop = new Map(data.stops.map((stop) => [stop.id, stop]));
  data.byService = new Map(data.services.map((service) => [service.id, service]));
  for (const service of data.services) {
    for (const direction of Object.values(service.directions)) {
      direction.projected = direction.geometry.map(projectSegment);
    }
  }
  return data;
}

function createDrawer() {
  const toggle = document.querySelector("#drawer-toggle");
  const sidebar = document.querySelector("#sidebar");
  function set(open) {
    sidebar.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", String(open));
  }
  toggle.addEventListener("click", () => set(!sidebar.classList.contains("open")));
  return set;
}

function etaText(seconds) {
  return seconds < 60 ? seconds + " sec" : Math.ceil(seconds / 60) + " min";
}

function mapDashboard(network, catalog) {
  let selection = null;
  let planner, simulation;
  const listUpdates = new Map();
  const popup = document.querySelector("#map-info");
  const setDrawer = createDrawer();
  const name = (id) => stopName(network, id);
  const selected = new Set();
  let routeMode = view === "routes" ? "all" : "default";
  let updateExplorer;
  const layers = document.querySelector(".map-layers");
  const layerInputs = new Map([...layers.querySelectorAll("[data-layer]")].map((input) => [input.dataset.layer, input]));
  let preferences = {};
  try { preferences = JSON.parse(localStorage.getItem("busadda-map-layers")) || {}; } catch { /* optional preference */ }

  function updateServices() {
    const active = new Set(selected);
    if (selection?.kind === "bus") active.add(simulation.vehicles.get(selection.id).service.id);
    if (selection?.kind === "service") active.add(selection.id);
    map.serviceSelection(active, routeMode);
    updateExplorer?.(selected, routeMode);
  }

  function setMode(mode) {
    routeMode = mode;
    if (view === "routes") {
      layerInputs.get("routes").checked = mode !== "none";
      map.setLayer("routes", mode !== "none");
    }
    updateServices();
  }

  function showService(id, fit = true) {
    const service = network.byService.get(id);
    if (view === "routes" && !layerInputs.get("stops").checked) {
      layerInputs.get("stops").checked = true;
      map.setLayer("stops", true);
    }
    setupPopup("service", id, "Bus " + service.number, "BUS ROUTE");
    if (view === "routes") selected.add(id);
    if (!layerInputs.get("routes").checked) {
      layerInputs.get("routes").checked = true;
      map.setLayer("routes", true);
    }
    if (routeMode === "none") setMode("selected");
    updateServices();
    serviceDetails(popup, network, service, (stopId) => {
      map.highlightStop(stopId, true);
      popup.querySelector(".stop-focus-status").textContent = "Map centered on " + name(stopId) + ".";
    });
    const status = el("p", "stop-focus-status");
    status.setAttribute("role", "status");
    popup.append(status);
    if (fit) {
      map.fit(map.servicePoints);
      setDrawer(false);
    }
  }

  function closePopup() {
    popup.hidden = true;
    selection = null;
    map.highlightStop(null);
    updateServices();
    simulation?.vehicles.forEach((bus) => bus.marker.classList.remove("focused"));
  }

  function setupPopup(kind, id, title, subtitle) {
    closePopup();
    selection = { kind, id };
    const close = button("", "icon-button popup-close", "close");
    close.setAttribute("aria-label", "Close map details");
    close.addEventListener("click", closePopup);
    popup.replaceChildren(close, el("p", "eyebrow", subtitle), el("h3", null, title));
    popup.hidden = false;
  }

  function showStop(id, focus = false) {
    const stop = network.byStop.get(id);
    setupPopup("stop", id, stop.name, stop.locality.toUpperCase());
    map.highlightStop(id, focus);
    popup.append(el("p", null, stop.lat.toFixed(4) + "° N · " + stop.lon.toFixed(4) + "° E"),
      el("p", null, "Bus services · " + stop.services.map((sid) => network.byService.get(sid).number).join(", ")),
      el("p", null, "Connected stops · " + stop.neighbors.map(name).join(", ")));
    const actions = el("div", "journey-actions");
    for (const [kind, label] of [["from", "Set as source"], ["to", "Set as destination"]]) {
      if (planner) {
        const control = button(label, "button secondary", "pin");
        control.addEventListener("click", () => {
          planner.setStop(kind, id);
          closePopup();
          setDrawer(true);
          planner.pickers[kind].input.focus();
          planner.pickers[kind].close();
        });
        actions.append(control);
      } else {
        const control = el("a", "button secondary", label);
        control.href = "/plan?" + kind + "=" + id;
        actions.append(control);
      }
    }
    popup.append(actions);
    if (focus) {
      setDrawer(false);
      popup.querySelector("button").focus({ preventScroll: true });
    }
  }

  function showBus(id, focus = false) {
    const data = simulation.current(id);
    if (focus) {
      layerInputs.get("buses").checked = true;
      simulation.show(true);
    }
    setupPopup("bus", id, "Bus " + data.bus.service.number, "SIMULATED VEHICLE");
    if (routeMode !== "none" && layerInputs.get("routes").checked) updateServices();
    popup.append(el("p", "service-title", data.bus.service.name));
    data.bus.marker.classList.add("focused");
    if (focus) map.focusPoint(data.position);
    for (const key of ["location", "next", "direction", "eta"]) {
      const row = el("p");
      row.dataset.busInfo = key;
      popup.append(row);
    }
    const highlight = button("Highlight full route", "button secondary", "route");
    highlight.addEventListener("click", () => {
      if (routeMode === "none") setMode("selected");
      layerInputs.get("routes").checked = true;
      map.setLayer("routes", true);
      updateServices();
      map.fit(map.servicePoints);
    });
    popup.append(highlight);
    update();
    if (focus) {
      setDrawer(false);
      popup.querySelector("button").focus({ preventScroll: true });
    }
  }

  function update() {
    if (selection?.kind === "bus") {
      const data = simulation.current(selection.id);
      const set = (key, value) => { popup.querySelector('[data-bus-info="' + key + '"]').textContent = value; };
      set("location", data.step.moving ? name(data.step.from) + " → " + name(data.step.to) : "At " + name(data.step.to));
      set("next", "Next stop · " + name(data.next));
      set("direction", "Direction · " + name(data.toward));
      set("eta", data.status + " · ETA " + etaText(data.eta));
    }
    listUpdates.forEach((node, id) => {
      const data = simulation.current(id);
      node.textContent = data.status + " · " + name(data.next) + " · " + etaText(data.eta);
    });
  }

  const map = new TransitMap(document.querySelector("#map"), network, showStop, showBus, showService, closePopup);
  simulation = new BusSimulation(network, map, update);
  for (const [layer, input] of layerInputs) {
    if (preferences[layer] === false) input.checked = false;
    const apply = () => {
      if (layer === "buses") {
        simulation.show(input.checked);
        if (!input.checked && selection?.kind === "bus") closePopup();
      } else if (view === "routes" && layer === "routes") {
        setMode(input.checked ? (routeMode === "none" ? "all" : routeMode) : "none");
      } else {
        map.setLayer(layer, input.checked);
      }
    };
    input.addEventListener("change", () => {
      apply();
      preferences[layer] = input.checked;
      try { localStorage.setItem("busadda-map-layers", JSON.stringify(preferences)); } catch { /* optional preference */ }
    });
    apply();
  }
  document.querySelector("#map-stats").hidden = true;

  if (view === "plan") {
    planner = new RoutePlanner(network, catalog, map, simulation, { closePopup, closeDrawer: () => setDrawer(false), showStop: (id) => showStop(id, true) });
    return;
  }
  if (view === "routes") {
    updateExplorer = serviceExplorer(network, (id) => {
      if (selected.has(id)) {
        selected.delete(id);
        closePopup();
      } else {
        showService(id);
      }
    }, setMode, () => {
      selected.clear();
      closePopup();
    });
    updateServices();
    return;
  }

  const search = document.querySelector("#directory-search");
  const region = document.querySelector("#region");
  const directory = document.querySelector("#directory");
  const buses = view === "buses";
  const entries = buses ? network.vehicles.map((vehicle) => ({
    ...vehicle, ...network.byService.get(vehicle.service), id: vehicle.id,
  })) : network.stops;
  for (const value of [...new Set(entries.map((entry) => buses ? entry.region : entry.locality))].sort()) {
    const option = el("option", null, value);
    option.value = value;
    region.append(option);
  }
  function filter() {
    const term = search.value.trim().toLowerCase();
    listUpdates.clear();
    directory.replaceChildren();
    for (const entry of entries) {
      const entryRegion = buses ? entry.region : entry.locality;
      const title = (buses ? entry.number + " · " : "") + entry.name;
      if (!(title + " " + entryRegion).toLowerCase().includes(term) || (region.value && region.value !== entryRegion)) continue;
      const card = button("", "directory-item");
      card.append(el("strong", null, title));
      if (buses) {
        const details = el("small");
        listUpdates.set(entry.id, details);
        card.append(details, miniRoute(entry));
      } else {
        card.append(el("small", null, entry.locality + " · " + entry.services.length +
          (entry.services.length === 1 ? " service" : " services")));
      }
      card.addEventListener("click", () => {
        (buses ? showBus : showStop)(entry.id, true);
      });
      directory.append(card);
    }
    if (!directory.children.length) directory.append(el("p", "muted", "No matches. Try a different search or region."));
    update();
  }
  search.addEventListener("input", filter);
  region.addEventListener("change", filter);
  filter();
}

function miniRoute(service) {
  const segments = service.directions[0].projected;
  const points = segments.flatMap((segment) => segment.points);
  const xs = points.map(([x]) => x), ys = points.map(([, y]) => y);
  const pad = 15;
  const x = Math.min(...xs) - pad, y = Math.min(...ys) - pad;
  const width = Math.max(...xs) - x + pad, height = Math.max(...ys) - y + pad;
  const node = svg("svg", { viewBox: [x, y, width, height].join(" "), preserveAspectRatio: "xMinYMid meet", "aria-hidden": "true" });
  node.append(svg("path", { d: corridorPath(segments), fill: "none", stroke: service.color,
    "stroke-width": 1.4, "vector-effect": "non-scaling-stroke" }));
  for (const [cx, cy] of [points[0], points.at(-1)]) node.append(svg("circle", { cx, cy, r: 5, fill: service.color }));
  return node;
}

async function showSaved(network, list) {
  const data = await api("saved");
  list.replaceChildren();
  if (!data.routes.length) {
    const empty = el("div", "panel saved-card");
    const link = el("a", "button primary", "Plan a route");
    link.href = "/plan";
    empty.append(el("p", "muted", "No saved routes yet."), el("small", null, "Save a journey from its results panel."), link);
    list.append(empty);
    return;
  }
  for (const journey of data.routes) {
    const card = el("article", "panel saved-card");
    card.append(el("p", "eyebrow", modeNames[journey.mode].toUpperCase()),
      el("h2", null, stopName(network, journey.source) + " → " + stopName(network, journey.destination)),
      el("small", null, "Saved " + new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(new Date(journey.created))));
    const actions = el("div", "saved-actions");
    const open = el("a", "button secondary", "View Route");
    open.href = routeURL(journey.source, journey.destination, journey.mode);
    const calculate = button("Recalculate Route", "button secondary", "route");
    calculate.addEventListener("click", async () => {
      calculate.disabled = true;
      try {
        const result = await api("route", "POST", { source: journey.source, destination: journey.destination, mode: journey.mode });
        card.querySelector("small").textContent = result.km + " km · " + result.minutes + " min · " +
          result.interchanges.length + (result.interchanges.length === 1 ? " interchange" : " interchanges");
        notify("Route recalculated.");
      } catch (error) { notify(error.message); }
      finally { calculate.disabled = false; }
    });
    const remove = button("Delete Route", "button secondary", "trash");
    remove.addEventListener("click", async () => {
      remove.disabled = true;
      try {
        await api("saved/" + journey.id, "DELETE");
        await showSaved(network, list);
        notify("Saved route deleted.");
      } catch (error) {
        remove.disabled = false;
        notify(error.message);
      }
    });
    actions.append(open, calculate, remove);
    card.append(actions);
    list.append(card);
  }
}

async function init() {
  if (view === "profile") return;
  try {
    const network = await readNetwork();
    if (view === "saved") {
      await showSaved(network, document.querySelector("#saved-list"));
    } else {
      if (!network.stops.length) throw new Error("The bus network is empty. Run the seed-network command.");
      let catalog = [];
      if (view === "plan") {
        try {
          const response = await fetch("/static/data/delhi-ncr-places.json");
          if (!response.ok) throw new Error("Place index request failed.");
          catalog = await response.json();
        } catch {
          notify("Landmark search is temporarily unavailable. You can still search by bus stop or coordinates.");
        }
      }
      mapDashboard(network, catalog);
    }
  } catch (error) {
    const target = document.querySelector("#map-stats") || document.querySelector("#saved-list");
    target.textContent = error.message;
    target.hidden = false;
    notify(error.message);
  }
}

const menu = document.querySelector(".account");
const navToggle = document.querySelector("#nav-toggle");
navToggle.addEventListener("click", () => {
  navToggle.setAttribute("aria-expanded", String(navToggle.getAttribute("aria-expanded") !== "true"));
});
document.addEventListener("click", (event) => {
  if (!menu.contains(event.target)) menu.open = false;
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menu.open) {
    menu.open = false;
    menu.querySelector("summary").focus();
  }
});
init();
