import { project } from "./geography.js";

export function corridorPath(segments) {
  return segments.map(({ points }, index) =>
    (index === 0 ? "M " : " L ") + points.map((point) => point.join(",")).join(" L "),
  ).join("");
}

export function projectSegment(coordinates) {
  const points = coordinates.map(([lat, lon]) => project(lat, lon));
  let total = 0;
  const offsets = [0];
  for (let i = 1; i < points.length; i++) {
    total += Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
    offsets.push(total);
  }
  return { points, offsets, total };
}

export function pointOnSegment({ points, offsets, total }, progress) {
  const distance = Math.max(0, Math.min(1, progress)) * total;
  for (let i = 1; i < points.length; i++) {
    if (distance <= offsets[i] && offsets[i] > offsets[i - 1]) {
      const t = (distance - offsets[i - 1]) / (offsets[i] - offsets[i - 1]);
      return points[i - 1].map((start, axis) => start + (points[i][axis] - start) * t);
    }
  }
  return points.at(-1);
}
