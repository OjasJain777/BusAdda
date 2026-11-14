import { createPlaceSearch, stopDistance } from "./place-search.js";
import { api, button, el, icon, notify, stopName } from "./ui.js";

export class StopPicker {
  constructor(container, autocomplete) {
    this.container = container;
    this.input = container.querySelector("input");
    this.list = container.querySelector("ul");
    this.clear = container.querySelector("button");
    this.autocomplete = autocomplete;
    this.hint = container.querySelector(".nearest-stop-hint");
    this.selected = null;
    this.index = -1;
    this.input.addEventListener("input", () => {
      this.selected = null;
      this.hint.hidden = true;
      this.clear.hidden = !this.input.value;
      this.render();
    });
    this.input.addEventListener("focus", () => this.render());
    this.input.addEventListener("keydown", (event) => this.keydown(event));
    this.clear.addEventListener("click", () => {
      this.set(null);
      this.input.focus();
    });
    container.addEventListener("focusout", (event) => {
      if (!container.contains(event.relatedTarget)) this.close();
    });
  }

  set(result, text = "") {
    this.selected = result;
    this.input.value = result?.place || result?.stop.name || text;
    this.hint.hidden = !result?.place;
    if (result?.place) {
      this.hint.textContent = result.stop.name + " · " + stopDistance(result.km) + " straight-line";
    }
    this.clear.hidden = !this.input.value;
    this.close();
  }

  value() {
    if (this.selected) return this.selected;
    const query = this.input.value.trim().toLowerCase();
    if (!query) return null;
    const matches = this.autocomplete(this.input.value);
    const exactStop = matches.find((result) => !result.place && result.exact);
    if (exactStop) return exactStop;
    const exact = matches.filter((result) =>
      (result.place || result.stop.name).toLowerCase() === query || result.exact,
    );
    return exact.length === 1 ? exact[0] : null;
  }

  render() {
    this.matches = this.autocomplete(this.input.value);
    this.list.replaceChildren();
    this.index = -1;
    this.input.removeAttribute("aria-activedescendant");
    this.matches.forEach((result, index) => {
      const { stop, place, km } = result;
      const item = el("li");
      item.id = this.input.id + "-match-" + index;
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", "false");
      item.append(el("strong", null, place || stop.name), el("small", null, place
        ? "Nearest stop: " + stop.name + " · " + stopDistance(km) + " straight-line"
        : stop.locality));
      item.addEventListener("pointerdown", (event) => event.preventDefault());
      item.addEventListener("click", () => this.set(result));
      this.list.append(item);
    });
    if (!this.matches.length) {
      const empty = el("li", "muted", "Place not found in Delhi NCR. Try a nearby landmark or enter latitude, longitude.");
      empty.setAttribute("role", "presentation");
      this.list.append(empty);
    }
    this.list.hidden = false;
    this.input.setAttribute("aria-expanded", "true");
  }

  close() {
    this.list.hidden = true;
    this.input.setAttribute("aria-expanded", "false");
    this.input.removeAttribute("aria-activedescendant");
  }

  keydown(event) {
    if (event.key === "Escape") this.close();
    if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      if (this.list.hidden) this.render();
      if (!this.matches.length) return;
      const last = this.matches.length - 1;
      this.index = event.key === "ArrowDown" ? Math.min(last, this.index + 1) : Math.max(0, this.index - 1);
      [...this.list.children].forEach((node, i) => node.setAttribute("aria-selected", String(i === this.index)));
      const active = this.list.children[this.index];
      this.input.setAttribute("aria-activedescendant", active.id);
      active.scrollIntoView({ block: "nearest" });
    }
    if (event.key === "Enter" && !this.list.hidden && this.index >= 0) {
      event.preventDefault();
      this.set(this.matches[this.index]);
    }
  }
}

export const modeNames = { shortest: "Shortest Route", interchanges: "Minimum Interchange" };

export function routeURL(source, destination, mode) {
  return "/plan?" + new URLSearchParams({ from: source, to: destination, mode, search: "1" });
}

export class RoutePlanner {
  constructor(network, catalog, map, simulation, options) {
    this.network = network;
    this.map = map;
    this.simulation = simulation;
    this.options = options;
    this.form = document.querySelector("#route-form");
    this.error = document.querySelector("#route-error");
    this.find = document.querySelector("#find-route");
    this.status = document.querySelector("#route-loading");
    this.panel = document.querySelector("#journey-panel");
    this.pickers = {};
    const autocomplete = createPlaceSearch(network.stops, catalog);
    for (const container of this.form.querySelectorAll("[data-picker]")) {
      this.pickers[container.dataset.picker] = new StopPicker(container, autocomplete);
    }
    this.form.addEventListener("submit", (event) => {
      event.preventDefault();
      this.search();
    });
    document.querySelector("#swap").addEventListener("click", () => {
      const { from, to } = this.pickers;
      const source = from.value(), destination = to.value();
      const originalSource = from.input.value;
      from.set(destination, to.input.value);
      to.set(source, originalSource);
    });
    for (const [source, destination] of network.presets) {
      const preset = button(stopName(network, source) + " → " + stopName(network, destination), "preset");
      preset.append(icon("arrow", 14));
      preset.addEventListener("click", () => {
        this.setStop("from", source);
        this.setStop("to", destination);
        this.search();
      });
      document.querySelector("#presets").append(preset);
    }
    const params = new URLSearchParams(location.search);
    for (const kind of ["from", "to"]) this.setStop(kind, Number(params.get(kind)));
    const mode = params.get("mode");
    if (Object.hasOwn(modeNames, mode)) this.form.elements.mode.value = mode;
    if (params.get("search") === "1") this.search();
  }

  setStop(kind, id) {
    const stop = this.network.byStop.get(id);
    this.pickers[kind].set(stop ? { stop } : null);
  }

  showError(message) {
    this.error.textContent = message;
    this.error.hidden = !message;
  }

  async search() {
    if (this.find.disabled) return;
    const from = this.pickers.from.value();
    const to = this.pickers.to.value();
    const source = from?.stop;
    const target = to?.stop;
    this.showError("");
    if (!source || !target) {
      this.showError("Choose a place or bus stop from the suggestions for both fields.");
      this.pickers[source ? "to" : "from"].input.focus();
      return;
    }
    if (source.id === target.id) {
      this.showError("Both selections use the same bus stop. Choose a different stop.");
      this.pickers.to.input.focus();
      return;
    }
    this.pickers.from.set(from);
    this.pickers.to.set(to);
    const mode = this.form.elements.mode.value;
    this.find.disabled = true;
    this.find.setAttribute("aria-busy", "true");
    this.find.querySelector("span").textContent = "Finding route…";
    this.status.textContent = "Finding route…";
    try {
      const [result] = await Promise.all([
        api("route", "POST", { source: source.id, destination: target.id, mode }),
        new Promise((resolve) => setTimeout(resolve, 400)),
      ]);
      this.options.closePopup();
      this.options.closeDrawer();
      this.simulation.stopJourney();
      this.render(result, { from, to });
      this.map.drawRoute(result, this.network, { from, to });
      history.replaceState(null, "", routeURL(source.id, target.id, mode));
    } catch (error) {
      this.showError(error.message);
      notify(error.message);
    } finally {
      this.find.disabled = false;
      this.find.removeAttribute("aria-busy");
      this.status.textContent = "";
      this.find.querySelector("span").textContent = "Find Route";
    }
  }

  render(journey, { from, to }) {
    const network = this.network;
    const name = (id) => stopName(network, id);
    const title = el("div");
    title.append(el("p", "eyebrow", journey.mode_label.toUpperCase()), el("h2", null,
      name(journey.source) + " → " + name(journey.destination)));
    const access = [from, to].filter((result) => result.place);
    for (const result of access) {
      title.append(el("p", "journey-access", result.place + " · " + stopDistance(result.km) +
        " straight-line to " + result.stop.name));
    }
    const metrics = el("div", "journey-metrics");
    for (const [value, label] of [[journey.km + " km", "Distance"], [journey.minutes + " min", "Est. time"],
      [journey.interchanges.length, "Interchanges"], [journey.stops.length, "Stops"]]) {
      const metric = el("div", "metric");
      metric.append(el("strong", null, value), el("span", null, label));
      metrics.append(metric);
    }
    const top = el("div", "journey-top");
    top.append(title, metrics);
    const details = el("details", "journey-details");
    details.open = !matchMedia("(max-width: 760px)").matches;
    details.append(el("summary", null, "Journey timeline"));
    const stopButton = (id) => {
      const control = button(name(id), "journey-stop-button");
      control.addEventListener("click", () => this.options.showStop(id));
      return control;
    };
    const timeline = el("ol", "timeline");
    timeline.setAttribute("aria-label", "Bus legs and interchanges");
    for (const [index, leg] of journey.legs.entries()) {
      if (index) {
        const change = el("li", "transfer-card");
        change.append(el("span", null, "Interchange"), stopButton(leg.from),
          el("small", null, "~" + journey.transfer_minutes + " min"));
        timeline.append(change);
      }
      const card = el("li", "leg");
      card.dataset.color = index % 6;
      const label = el("span", "bus-label");
      label.append(icon("bus", 13), document.createTextNode("Bus " + leg.number));
      const boarding = el("p", "leg-stop");
      boarding.append("Board at ", stopButton(leg.from));
      const alighting = el("p", "leg-stop");
      alighting.append("Alight at ", stopButton(leg.to));
      card.append(label, boarding, alighting,
        el("small", null, leg.km + " km · " + leg.minutes + " min"));
      const stops = leg.stops.slice(1, -1);
      if (stops.length) {
        const intermediate = el("details");
        intermediate.append(el("summary", null, stops.length + " intermediate " + (stops.length === 1 ? "stop" : "stops")));
        const list = el("ol", "intermediate");
        for (const id of stops) {
          const item = el("li");
          item.append(stopButton(id));
          list.append(item);
        }
        intermediate.append(list);
        card.append(intermediate);
      }
      timeline.append(card);
    }
    details.append(timeline);
    const actions = el("div", "journey-actions");
    const save = button("Save Route", "button secondary", "bookmark");
    const clear = button("Clear Route", "button secondary", "close");
    const start = button("Start Journey Simulation", "button secondary", "play");
    const status = el("span", "journey-status");
    status.setAttribute("role", "status");
    save.addEventListener("click", async () => {
      save.disabled = true;
      try {
        await api("saved", "POST", { source: journey.source, destination: journey.destination, mode: journey.mode });
        notify("Journey saved to Saved Routes.");
      } catch (error) {
        notify(error.message);
      } finally {
        save.disabled = false;
      }
    });
    clear.addEventListener("click", () => {
      this.options.closePopup();
      this.simulation.stopJourney();
      this.map.drawRoute(null, network);
      this.map.reset();
      this.panel.replaceChildren();
      this.panel.hidden = true;
      history.replaceState(null, "", "/plan");
      this.find.focus({ preventScroll: true });
    });
    start.addEventListener("click", () => {
      if (start.dataset.running === "true") {
        this.simulation.stopJourney();
        start.dataset.running = "false";
        start.lastChild.textContent = "Start Journey Simulation";
        status.textContent = "Simulation stopped.";
        return;
      }
      start.dataset.running = "true";
      start.lastChild.textContent = "Stop Simulation";
      this.simulation.startJourney(journey, network, (message, complete) => {
        status.textContent = message;
        if (complete) {
          start.dataset.running = "false";
          start.lastChild.textContent = "Replay Journey";
        }
      });
    });
    if (document.querySelector(".account")) actions.append(save);
    actions.append(clear, start, status);
    this.panel.replaceChildren(top, details, actions);
    this.panel.hidden = false;
  }
}
