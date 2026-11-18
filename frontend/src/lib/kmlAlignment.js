import { detectTracks } from './api.js';
import { DEFAULTS } from './config.js';

/** Same metric polyline length and default loop limits as /main-center. */
export function getTrackCentre(track) {
  const points = track?.pts_utm;
  if (!Array.isArray(points) || points.length < 2) {
    throw new Error('No usable continuous track alignment was found in this KML.');
  }

  let length = 0;
  for (let i = 0; i < points.length; i++) {
    const point = points[i];
    if (!Array.isArray(point) || !Number.isFinite(point[0]) || !Number.isFinite(point[1])) {
      throw new Error('The selected track contains invalid metric coordinates.');
    }
    if (i > 0) {
      length += Math.hypot(point[0] - points[i - 1][0], point[1] - points[i - 1][1]);
    }
  }
  if (!Number.isFinite(length)) {
    throw new Error('The selected track has an invalid length.');
  }

  const loopLength = DEFAULTS.crossoverDistance;
  if (length < loopLength) {
    throw new Error(`MAIN track is only ${length.toFixed(1)}m — a fixed ${loopLength}m loop cannot fit.`);
  }

  // Use the coordinates, not the detector's length_m label rounded to 2 decimals.
  const centre = length / 2;
  const halfLoop = loopLength / 2;
  const round = (value) => Number(value.toFixed(3));
  return {
    main_length_m: round(length),
    main_center_m: round(centre),
    default_c1_m: round(centre - halfLoop),
    default_c2_m: round(centre + halfLoop),
  };
}

/** One KML upload; reuse its detected geometry for the default track's centre. */
export async function loadKmlAlignment(kmlFile) {
  const response = await detectTracks({ kmlFile });
  const tracks = Array.isArray(response?.candidate_tracks) ? response.candidate_tracks : [];
  const track = tracks[0];
  return { tracks, track, centre: getTrackCentre(track) };
}
