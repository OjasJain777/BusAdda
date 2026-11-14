import { pointOnSegment } from "./route-geometry.js";

const simulationRate = 4;

function assembledRun(service, vehicle, dwellSeconds) {
  const steps = [];
  let time = 0;
  for (const direction of [vehicle.direction, 1 - vehicle.direction]) {
    const { stops, segments, projected } = service.directions[direction];
    for (const [index, km] of segments.entries()) {
      const ride = km / vehicle.speed * 3600 / simulationRate;
      steps.push({ from: stops[index], to: stops[index + 1], begin: time, end: time + ride,
        toward: stops.at(-1), geometry: projected[index], moving: true });
      time += ride;
      steps.push({ from: stops[index + 1], to: stops[index + 1], begin: time, end: time + dwellSeconds / simulationRate,
        toward: stops.at(-1), moving: false });
      time += dwellSeconds / simulationRate;
    }
  }
  return { steps, time };
}

export class BusSimulation {
  constructor(network, map, onUpdate) {
    this.map = map;
    this.epoch = network.now - performance.now();
    this.onUpdate = onUpdate;
    this.visible = true;
    this.frame = null;
    this.lastUpdate = -Infinity;
    this.reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
    this.vehicles = new Map(network.vehicles.map((vehicle) => {
      const service = network.byService.get(vehicle.service);
      return [vehicle.id, { ...vehicle, service, ...assembledRun(service, vehicle, network.dwell),
        marker: map.addBus(vehicle, service) }];
    }));
    this.tick = this.tick.bind(this);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        if (this.frame !== null) cancelAnimationFrame(this.frame);
        this.frame = null;
      } else {
        this.schedule();
      }
    });
    this.schedule();
  }

  current(id, now = performance.now()) {
    const bus = this.vehicles.get(id);
    const elapsed = (this.epoch + now - bus.start) / 1000 + bus.time * bus.progress;
    const t = ((elapsed % bus.time) + bus.time) % bus.time;
    const index = bus.steps.findIndex((step) => t < step.end);
    const step = bus.steps[index];
    const progress = (t - step.begin) / (step.end - step.begin);
    const next = step.moving ? step : bus.steps[(index + 1) % bus.steps.length];
    const remaining = next.end - t + (next.begin < step.begin ? bus.time : 0);
    return { bus, step, next: next.to, toward: next.toward, eta: Math.ceil(remaining * simulationRate),
      position: step.moving ? pointOnSegment(step.geometry, progress) : this.map.points.get(step.to),
      status: !step.moving ? "At stop" : remaining < 22 ? "Approaching stop" : "Moving" };
  }

  schedule() {
    if (this.frame === null && !document.hidden && (this.visible || this.journey)) {
      this.frame = requestAnimationFrame(this.tick);
    }
  }

  tick(now) {
    this.frame = null;
    const update = now - this.lastUpdate >= 800;
    if (this.visible && (!this.reducedMotion.matches || update)) {
      for (const id of this.vehicles.keys()) {
        const { bus, position } = this.current(id, now);
        bus.marker.setAttribute("transform", "translate(" + position.join(" ") + ")");
      }
    }
    if (update) {
      this.lastUpdate = now;
      this.onUpdate();
    }
    if (this.journey) this.runJourney(now);
    this.schedule();
  }

  show(visible) {
    this.visible = visible;
    if (!visible && this.frame !== null && !this.journey) {
      cancelAnimationFrame(this.frame);
      this.frame = null;
    }
    this.map.busLayer.setAttribute("visibility", visible ? "visible" : "hidden");
    this.map.busLayer.setAttribute("aria-hidden", String(!visible));
    for (const bus of this.vehicles.values()) bus.marker.setAttribute("tabindex", visible ? "0" : "-1");
    this.schedule();
  }

  startJourney(journey, network, update) {
    this.stopJourney();
    const steps = [];
    let end = 0;
    for (const [index, leg] of journey.legs.entries()) {
      const service = network.byService.get(leg.service);
      const direction = service.directions[leg.direction];
      const startIndex = direction.stops.indexOf(leg.from);
      leg.stops.slice(1).forEach((to, i) => {
        const from = leg.stops[i];
        const seconds = Math.max(.6, direction.segments[startIndex + i] / service.speed * 3600 / 110);
        steps.push({ from, to, geometry: direction.projected[startIndex + i], begin: end, end: end + seconds, message: "Riding bus " + leg.number + " · " + network.byStop.get(to).name });
        end += seconds;
      });
      if (index < journey.legs.length - 1) {
        steps.push({ from: leg.to, to: leg.to, begin: end, end: end + 1.7,
          message: "Changing buses at " + network.byStop.get(leg.to).name });
        end += 1.7;
      }
    }
    this.journey = { steps, start: performance.now(), update, lastStep: null };
    this.map.journeyMarker.setAttribute("visibility", "visible");
    this.schedule();
  }

  runJourney(now) {
    const elapsed = (now - this.journey.start) / 1000;
    const step = this.journey.steps.find((item) => elapsed < item.end);
    if (!step) {
      const final = this.journey.steps.at(-1);
      this.positionJourney(this.map.points.get(final.to));
      this.journey.update("Arrived at destination.", true);
      this.journey = null;
      return;
    }
    if (step !== this.journey.lastStep) {
      this.journey.lastStep = step;
      this.journey.update(step.message, false);
    }
    const progress = this.reducedMotion.matches ? 0 : Math.max(0, (elapsed - step.begin) / (step.end - step.begin));
    this.positionJourney(step.geometry ? pointOnSegment(step.geometry, progress) : this.map.points.get(step.to));
  }

  positionJourney([x, y]) {
    this.map.journeyMarker.setAttribute("cx", x);
    this.map.journeyMarker.setAttribute("cy", y);
  }

  stopJourney() {
    this.journey = null;
    this.map.journeyMarker.setAttribute("visibility", "hidden");
  }
}
