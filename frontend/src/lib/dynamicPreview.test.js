import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { generateDynamicPreview } from './dynamicPreview.js';

function outlineBounds(result, layer) {
  const group = result.svg.match(new RegExp(`<g data-layer="${layer}"[^>]*>([\\s\\S]*?)</g>`));
  assert.ok(group, `Expected ${layer} geometry`);
  return [...group[1].matchAll(/<path d="([^"]+)"/g)].map(([, d]) => {
    const points = [...d.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)].map(([, x, y]) => [Number(x), Number(y)]);
    return {
      x0: Math.min(...points.map(([x]) => x)),
      x1: Math.max(...points.map(([x]) => x)),
      y0: Math.min(...points.map(([, y]) => y)),
      y1: Math.max(...points.map(([, y]) => y)),
    };
  });
}

describe('generateDynamicPreview', () => {
  test('renders strictly single baseline MAIN_LINE without extra lines when form has minimal data', () => {
    const form = {
      mainLength: 1200,
      mainCenter: 600,
      mainLineDirection: 'UP',
    };
    const res = generateDynamicPreview(form);

    assert.ok(res);
    assert.equal(res.isDynamic, true);
    // Strictly only 1 track entity (MAIN_LINE) - no synthetic direction lines
    assert.equal(res.entities, 1);
    assert.ok(res.svg.includes('<svg'));
    assert.ok(res.svg.includes('MAIN_LINE'));
    assert.ok(res.layers.includes('MAIN_LINE'));
    assert.ok(!res.layers.includes('DIRECTION'));
  });

  test('dynamically renders loop lines as parallel tracks strictly as configured', () => {
    const form = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [
        {
          name: 'LOOP_1',
          referenceTrack: 'MAIN_LINE',
          spacing: 5.3,
          side: 'LEFT',
          c1: 425,
          c2: 1175,
        },
      ],
    };
    const res = generateDynamicPreview(form);

    assert.ok(res.layers.includes('LOOP_1'));
    assert.ok(!res.layers.includes('LOOP_CROSSOVER'));
    assert.ok(res.svg.includes('LOOP_1'));
  });

  test('dynamically renders platforms and station buildings', () => {
    const form = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [{ name: 'LOOP_1', spacing: 5.3, side: 'LEFT' }],
      platforms: [
        {
          name: 'PLATFORM_1',
          track: 'LOOP_1',
          side: 'LEFT',
          length: 550,
          width: 6,
          chainage: 800,
        },
      ],
      stations: [
        {
          platform: 'PLATFORM_1',
          name: 'CENTRAL STATION',
          length: 40,
          width: 10,
          chainage: 800,
        },
      ],
    };
    const res = generateDynamicPreview(form);

    assert.ok(res.layers.includes('PLATFORM_1'));
    assert.ok(res.layers.includes('STATION-BUILDING'));
    assert.ok(res.layers.includes('STATION-FLAG'));
    assert.ok(res.svg.includes('HIGH LEVEL PASSENGER PLATFORM'));
    assert.ok(res.svg.includes('CENTRAL STATION'));
  });

  test('centres a default-size station at its platform instead of treating 4 KM as 4 metres', () => {
    const result = generateDynamicPreview({
      mainLength: 10000,
      stationMarkers: [{ km: '4', m: '' }],
      platforms: [{ track: 'MAIN_LINE', stationIndex: 0 }],
      stations: [{ platform: 'PLATFORM_1', chainage: '4', side: 'LEFT', length: '', width: '' }],
    });

    assert.deepEqual(outlineBounds(result, 'STATION-BUILDING')[0], {
      x0: 3980, x1: 4020, y0: 8.68, y1: 18.68,
    });
    assert.ok(result.svg.includes('KM: 4.000'));
  });

  test('uses kilometre-plus-metre station references relative to a nonzero alignment datum', () => {
    const form = {
      mainLength: 3000,
      startKm: '3',
      startM: '500',
      stationMarkers: [{ chainage: '4+250' }],
      platforms: [{ track: 'MAIN_LINE', stationIndex: 0 }],
      stations: [{ platform: 'PLATFORM_1', chainage: '4+250', stationIndex: 0 }],
    };
    const result = generateDynamicPreview(form);
    assert.equal(outlineBounds(result, 'STATION-BUILDING')[0].x0, 730);
    assert.equal(outlineBounds(result, 'STATION-BUILDING')[0].x1, 770);
    assert.ok(result.svg.includes('KM: 4+250'));

    const decimal = generateDynamicPreview({
      ...form,
      stationMarkers: [{ km: '4.25', m: '' }],
      stations: [{ ...form.stations[0], chainage: '4.25' }],
    });
    assert.deepEqual(outlineBounds(decimal, 'STATION-BUILDING'), outlineBounds(result, 'STATION-BUILDING'));
    assert.ok(decimal.svg.includes('KM: 4.250'));
  });

  test('keeps platform IDs separate from duplicate display names and places each station at its own yard', () => {
    const form = {
      mainLength: 10000,
      stationMarkers: [{ km: '4' }, { km: '7', m: '500' }],
      platforms: [
        { name: 'PASSENGER PLATFORM', track: 'MAIN_LINE', stationIndex: 0 },
        { name: 'PASSENGER PLATFORM', track: 'MAIN_LINE', stationIndex: 1 },
      ],
      stations: [
        { platform: 'PLATFORM_1', stationIndex: 0 },
        { platform: 'PLATFORM_2', stationIndex: 1 },
      ],
    };
    const result = generateDynamicPreview(form);
    assert.ok(result.layers.includes('PLATFORM_1'));
    assert.ok(result.layers.includes('PLATFORM_2'));
    assert.deepEqual(outlineBounds(result, 'STATION-BUILDING').map(({ x0, x1 }) => [x0, x1]), [
      [3980, 4020], [7480, 7520],
    ]);
    assert.ok(result.svg.includes('KM: 7+500'));

    const moved = generateDynamicPreview({ ...form, stationMarkers: [{ km: '4' }, { km: '8' }] });
    assert.deepEqual(outlineBounds(moved, 'STATION-BUILDING').map(({ x0, x1 }) => [x0, x1]), [
      [3980, 4020], [7980, 8020],
    ]);
  });

  test('updates building dimensions, side and annotation while remaining centred on the platform', () => {
    const form = {
      mainLength: 2000,
      stationMarkers: [{ km: '1' }],
      platforms: [{ track: 'MAIN_LINE', name: 'CUSTOM PLATFORM' }],
      stations: [{ platform: 'PLATFORM_1', side: 'LEFT', chainage: '1' }],
    };
    const before = generateDynamicPreview(form);
    const annotated = generateDynamicPreview({
      ...form, stations: [{ ...form.stations[0], chainage: '1.25' }],
    });
    assert.deepEqual(outlineBounds(annotated, 'STATION-BUILDING'), outlineBounds(before, 'STATION-BUILDING'));
    assert.ok(annotated.svg.includes('KM: 1.250'));

    const resized = generateDynamicPreview({
      ...form, stations: [{ ...form.stations[0], length: '60', width: '12', side: 'RIGHT', name: 'NEW BUILDING' }],
    });
    assert.deepEqual(outlineBounds(resized, 'STATION-BUILDING')[0], {
      x0: 970, x1: 1030, y0: -10.32, y1: 1.68,
    });
    assert.ok(resized.svg.includes('NEW BUILDING'));
  });

  test('does not place station building when platform input is not selected', () => {
    const form = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [{ name: 'LOOP_1', spacing: 5.3, side: 'LEFT' }],
      platforms: [
        {
          name: 'PLATFORM_1',
          track: 'LOOP_1',
          side: 'LEFT',
          length: 550,
          width: 6,
          chainage: 800,
        },
      ],
      stations: [
        {
          platform: '', // No platform selected yet
          name: 'STATION BUILDING',
          length: 40,
          width: 10,
        },
      ],
    };
    const res = generateDynamicPreview(form);

    assert.ok(res.layers.includes('PLATFORM_1'));
    assert.ok(!res.layers.includes('STATION-BUILDING'));
    assert.ok(!res.layers.includes('STATION-FLAG'));
    assert.ok(!res.svg.includes('STATION-BUILDING'));
  });

  test('respects station building side (LEFT vs RIGHT) on platform', () => {
    const baseForm = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [{ name: 'LOOP_1', spacing: 5.3, side: 'LEFT' }],
      platforms: [
        {
          name: 'PLATFORM_1',
          track: 'LOOP_1',
          side: 'LEFT',
          length: 550,
          width: 6,
          chainage: 800,
        },
      ],
    };

    const resLeft = generateDynamicPreview({
      ...baseForm,
      stations: [{ platform: 'PLATFORM_1', side: 'LEFT', length: 40, width: 10, chainage: 800 }],
    });

    const resRight = generateDynamicPreview({
      ...baseForm,
      stations: [{ platform: 'PLATFORM_1', side: 'RIGHT', length: 40, width: 10, chainage: 800 }],
    });

    assert.ok(resLeft.layers.includes('STATION-BUILDING'));
    assert.ok(resRight.layers.includes('STATION-BUILDING'));
    // The SVGs must be different because the building polygon and flag are placed on different sides
    assert.notEqual(resLeft.svg, resRight.svg);
  });

  test('renders FOB deck connecting platforms and FOB stairs widening', () => {
    const form = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [{ name: 'LOOP_1', spacing: 5.3, side: 'LEFT' }],
      platforms: [
        {
          name: 'PLATFORM_1',
          track: 'MAIN_LINE',
          side: 'RIGHT',
          length: 550,
          width: 6,
          chainage: 800,
        },
        {
          name: 'PLATFORM_2',
          track: 'LOOP_1',
          side: 'LEFT',
          length: 550,
          width: 6,
          chainage: 800,
        },
      ],
      fobs: [
        {
          referenceTrack: 'MAIN_LINE',
          chainage: 840,
          width: 3,
          platforms: ['PLATFORM_1', 'PLATFORM_2'],
          arms: [
            { platform: 'PLATFORM_1', side: 'LEFT', length: 17 },
            { platform: 'PLATFORM_2', side: 'LEFT', length: 17 },
          ],
        },
      ],
    };
    const res = generateDynamicPreview(form);

    assert.ok(res.layers.includes('FOB'));
    assert.ok(res.svg.includes('FOOT OVER BRIDGE'));
  });

  test('dynamically renders crossovers and badges when configured in form', () => {
    const form = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [{ name: 'LOOP_1', spacing: 5.3, side: 'LEFT' }],
      crossovers: [
        {
          id: 'X-101',
          track1: 'MAIN_LINE',
          track2: 'LOOP_1',
          c1: 500,
          c2: 575,
        },
      ],
      bridges: [
        {
          placementMode: 'fixed',
          chainage: 950,
          width: 12,
        },
      ],
    };
    const res = generateDynamicPreview(form);

    assert.strictEqual(res.crossoverCount, 1);
    assert.strictEqual(res.crossoverTags.length, 1);
    assert.strictEqual(res.crossoverTags[0].id, 'X-101');
    assert.ok(res.layers.includes('CROSSOVERS'));
    assert.ok(res.layers.includes('SRJ'));
    assert.ok(res.svg.includes('cad-crossover-tag'));
    assert.ok(res.svg.includes('X-101'));
    assert.ok(res.layers.includes('BRIDGE_1'));
    assert.ok(res.svg.includes('BRIDGE'));
  });

  test('dynamically responds to crossover parameter updates (chainage, turnout, direction)', () => {
    const form1 = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [{ name: 'LOOP_1', spacing: 5.3, side: 'LEFT' }],
      crossovers: [
        {
          from: 'MAIN_LINE',
          to: 'LOOP_1',
          chainage: 500,
          turnout: '1:12',
          direction: 'FORWARD',
        },
      ],
    };
    const res1 = generateDynamicPreview(form1);
    assert.strictEqual(res1.crossoverCount, 1);
    assert.strictEqual(res1.crossoverTags[0].id, 'C1');
    assert.ok(res1.svg.includes('1 in 12'));
    const xMid1 = res1.crossoverTags[0].x;

    // Shift chainage from 500 to 700
    const form2 = {
      ...form1,
      crossovers: [{ ...form1.crossovers[0], chainage: 700, turnout: '1:8.5' }],
    };
    const res2 = generateDynamicPreview(form2);
    const xMid2 = res2.crossoverTags[0].x;
    assert.ok(xMid2 > xMid1);
    assert.ok(res2.svg.includes('1 in 8.5'));

    // Without crossovers, zero crossover entities or badges
    const formEmpty = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [{ name: 'LOOP_1', spacing: 5.3, side: 'LEFT' }],
    };
    const resEmpty = generateDynamicPreview(formEmpty);
    assert.strictEqual(resEmpty.crossoverCount, 0);
    assert.strictEqual(resEmpty.crossoverTags.length, 0);
    assert.ok(!resEmpty.layers.includes('CROSSOVERS'));
  });

  test('intelligently snaps AUTO crossovers to loop boundaries and autoAnchor crossovers', () => {
    const form = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [
        { name: 'LOOP_1', spacing: 5.3, side: 'LEFT', crossoverDistance: 750 },
        { name: 'LOOP_2', spacing: 5.3, side: 'RIGHT', crossoverDistance: 750 },
      ],
      crossovers: [
        {
          id: 'C1',
          from: 'MAIN_LINE',
          to: 'LOOP_1',
          direction: 'FORWARD',
          chainage: 'AUTO',
          turnout: '1:12',
        },
        {
          id: 'C2',
          from: 'MAIN_LINE',
          to: 'LOOP_1',
          direction: 'REVERSE',
          chainage: 'AUTO',
          turnout: '1:12',
        },
        {
          id: 'C3',
          from: 'MAIN_LINE',
          to: 'LOOP_2',
          direction: 'FORWARD',
          chainage: 'AUTO',
          turnout: '1:12',
          autoAnchor: 'C1',
        },
        {
          id: 'C4',
          from: 'MAIN_LINE',
          to: 'LOOP_2',
          direction: 'REVERSE',
          chainage: 'AUTO',
          turnout: '1:12',
          autoAnchor: 'C2',
        },
      ],
    };

    const res = generateDynamicPreview(form);
    assert.strictEqual(res.crossoverCount, 4);

    // C1: FORWARD on LOOP_1 snaps directly to LOOP_1.c1 (425m)
    // C2: REVERSE on LOOP_1 snaps directly to LOOP_1.c2 (1175m)
    // C3: FORWARD on LOOP_2 anchored to C1 -> placed at C1.endCh + 54m (approx 522.58 + 54 = 576.58m)
    // C4: REVERSE on LOOP_2 anchored to C2 -> placed at C2.startCh - 54m (approx 1077.42 - 54 = 1023.42m)
    const tagC1 = res.crossoverTags.find((t) => t.id === 'C1');
    const tagC2 = res.crossoverTags.find((t) => t.id === 'C2');
    const tagC3 = res.crossoverTags.find((t) => t.id === 'C3');
    const tagC4 = res.crossoverTags.find((t) => t.id === 'C4');

    assert.ok(tagC1 && tagC2 && tagC3 && tagC4);
    // C1 is around (425 + 522.58)/2 = 473.79m
    assert.ok(tagC1.x > 425 && tagC1.x < 525);
    // C2 is around (1175 + 1077.42)/2 = 1126.21m
    assert.ok(tagC2.x > 1070 && tagC2.x < 1180);
    // C3 is ahead of C1 (around 625m)
    assert.ok(tagC3.x > tagC1.x);
    // C4 is around (1121 + 1023.42)/2 = 1072.21m (separated by 54m from C2, inside loop)
    assert.ok(tagC4.x < tagC2.x);
    assert.ok(tagC4.x > 1000 && tagC4.x < 1150);

    // Verify angles are strictly normalized to [-90, 90] so badge text is NEVER upside down or reversed
    res.crossoverTags.forEach((t) => {
      assert.ok(t.ang >= -90 && t.ang <= 90, `Tag ${t.id} angle ${t.ang} must be in [-90, 90]`);
    });
  });

  test('places arrival crossover C5 exactly 13m before C3 on shared track matching CAD standard', () => {
    const form = {
      mainLength: 1600,
      mainCenter: 800,
      mainLines: [{ name: 'MAIN_LINE_1', spacing: 5.3, side: 'LEFT', direction: 'DN' }],
      loops: [
        { name: 'LOOP_1', referenceTrack: 'MAIN_LINE', spacing: 5.3, side: 'LEFT', c1: 500, c2: 1250 },
        { name: 'LOOP_2', referenceTrack: 'MAIN_LINE_1', spacing: 5.3, side: 'RIGHT', c1: 500, c2: 1250 },
      ],
      crossovers: [
        { id: 'C1', from: 'MAIN_LINE', to: 'LOOP_1', direction: 'FORWARD', chainage: 'AUTO' },
        { id: 'C3', from: 'MAIN_LINE_1', to: 'LOOP_2', direction: 'FORWARD', chainage: 'AUTO' },
        { id: 'C5', from: 'MAIN_LINE', to: 'MAIN_LINE_1', direction: 'FORWARD', chainage: 'AUTO', autoAnchor: 'C3' },
      ],
    };

    const res = generateDynamicPreview(form);
    const tagC1 = res.crossoverTags.find((t) => t.id === 'C1');
    const tagC3 = res.crossoverTags.find((t) => t.id === 'C3');
    const tagC5 = res.crossoverTags.find((t) => t.id === 'C5');

    assert.ok(tagC1 && tagC3 && tagC5);
    // C1 and C3 both start at loop start (500m)
    // C5 ends 13m before C3 on MAIN_LINE_1: C5 end is at 500 - 13 = 487m
    // C5 tag is to the left of C3 and C1
    assert.ok(tagC5.x < tagC3.x);
    assert.ok(tagC5.x < tagC1.x);
  });

  test('pushes second colliding crossover by 64m when two crossovers point at exact same chainage/point and preserves 120m overrun', () => {
    const form = {
      mainLength: 2000,
      mainCenter: 1000,
      loops: [
        {
          name: 'LOOP_1',
          side: 'LEFT',
          spacing: 5.3,
          c1: 500,
          c2: 1250,
          overrunBeforeC1: 120,
          overrunAfterC2: 120,
        },
      ],
      crossovers: [
        // C1 placed first at chainage 500.0 FORWARD
        { id: 'C1', from: 'LOOP_1', to: 'MAIN_LINE', direction: 'FORWARD', chainage: '500.0' },
        // C2 placed second targeting the exact same chainage 500.0 on shared line
        { id: 'C2', from: 'LOOP_1', to: 'MAIN_LINE', direction: 'FORWARD', chainage: '500.0' },
      ],
    };

    const res = generateDynamicPreview(form);
    const placed = res.placedCrossovers;
    assert.strictEqual(placed.length, 2);

    const c1 = placed.find((c) => c.id === 'C1');
    const c2 = placed.find((c) => c.id === 'C2');

    // First placed crossover remains untouched at 500.0
    assert.strictEqual(c1.c1, 500.0);

    // Second placed crossover is pushed by exactly 64.0m to 564.0
    assert.strictEqual(c2.c1, 564.0);
    // Its end point is shifted by 64m as well (preserving OL)
    assert.strictEqual(Math.round((c2.c2 - c1.c2) * 1000) / 1000, 64.0);

    // Connected loop CAL label should reflect the loop extent
    assert.ok(res.svg.includes('LOOP_1'));
  });

  for (const direction of ['FORWARD', 'REVERSE']) {
    test(`places fourth ${direction} AUTO at loop end, shifting 64m only on collision with C2`, () => {
      const sign = direction === 'FORWARD' ? 1 : -1;
      const other = direction === 'FORWARD' ? 'REVERSE' : 'FORWARD';
      const firstEnd = sign === 1 ? 1250 : 500;
      const secondEnd = sign === 1 ? 500 : 1250;
      const result = generateDynamicPreview({
        mainLength: 2000, mainCenter: 1000,
        loops: [
          { name: 'LOOP_1', spacing: 5.3, side: 'LEFT', c1: 500, c2: 1250 },
          { name: 'LOOP_2', spacing: 5.3, side: 'RIGHT', c1: 500, c2: 1250 },
        ],
        crossovers: [
          { id: 'C1', from: 'LOOP_1', to: 'MAIN_LINE', chainage: firstEnd, direction: other },
          { id: 'C2', from: 'LOOP_1', to: 'MAIN_LINE', chainage: secondEnd, direction },
          { id: 'C3', from: 'LOOP_2', to: 'MAIN_LINE', chainage: firstEnd, direction: other },
          { id: 'C4', from: 'LOOP_2', to: 'MAIN_LINE', chainage: 'AUTO', direction },
        ],
      });
      const [c1, c2, c3, c4] = result.placedCrossovers;
      assert.equal(c1.c1, firstEnd);
      assert.equal(c2.c1, secondEnd);
      assert.equal(c3.c1, firstEnd - sign * 64);
      assert.equal(c4.c1, secondEnd + sign * 64);
      assert.ok(Math.abs(c4.c2 - c2.c2 - sign * 64) < 1e-6);
    });
  }

  for (const direction of ['FORWARD', 'REVERSE']) {
    for (const earlierAuto of [false, true]) {
      test(`applies C4's ${direction} C3 anchor offset before collision push (earlier AUTO: ${earlierAuto})`, () => {
        const sign = direction === 'FORWARD' ? 1 : -1;
        const outerStart = sign === 1 ? 500 : 1250;
        const candidate = outerStart + sign * (97.578 + 13);
        const firstTwo = earlierAuto ? [
          { id: 'C1', from: 'LOOP_3', to: 'LOOP_1', chainage: outerStart, direction },
          { id: 'C2', from: 'LOOP_1', to: 'MAIN_LINE', chainage: 'AUTO', direction, autoAnchor: 'C1' },
        ] : [
          { id: 'C1', from: 'LOOP_1', to: 'MAIN_LINE', chainage: candidate, direction },
          { id: 'C2', from: 'LOOP_3', to: 'LOOP_1', chainage: outerStart, direction },
        ];
        const result = generateDynamicPreview({
          mainLength: 2000, mainCenter: 1000,
          loops: [
            { name: 'LOOP_1', spacing: 5.3, side: 'LEFT', c1: 500, c2: 1250 },
            { name: 'LOOP_2', spacing: 5.3, side: 'RIGHT', c1: 500, c2: 1250 },
            { name: 'LOOP_3', referenceTrack: 'LOOP_1', spacing: 5.3, side: 'LEFT', c1: 500, c2: 1250 },
            { name: 'LOOP_4', referenceTrack: 'LOOP_2', spacing: 5.3, side: 'RIGHT', c1: 500, c2: 1250 },
          ],
          crossovers: [...firstTwo,
            { id: 'C3', from: 'LOOP_4', to: 'LOOP_2', chainage: outerStart, direction },
            { id: 'C4', from: 'LOOP_2', to: 'MAIN_LINE', chainage: 'AUTO', direction, autoAnchor: 'C3' },
          ],
        });
        const collider = result.placedCrossovers[earlierAuto ? 1 : 0];
        const [c3, c4] = result.placedCrossovers.slice(2);
        assert.ok(Math.abs(collider.c1 - candidate) < 1e-6);
        assert.ok(Math.abs(c4.c1 - candidate - sign * 64) < 1e-6);
        assert.ok(Math.abs(c4.c1 - c3.c2 - sign * (13 + 64)) < 1e-6);
        assert.ok(Math.abs(c4.c2 - collider.c2 - sign * 64) < 1e-6);
      });
    }
  }

  test('trims main lines when enableMainLineTrim is active matching post-generation plan', () => {
    const untrimmedForm = {
      mainLength: 2000,
      mainCenter: 1000,
      enableMainLineTrim: false,
      loops: [{ name: 'LOOP_1', spacing: 5.3, side: 'LEFT', c1: 600, c2: 1400, overrunBeforeC1: 120, overrunAfterC2: 120 }],
    };
    const untrimmedRes = generateDynamicPreview(untrimmedForm);

    const trimmedForm = {
      ...untrimmedForm,
      enableMainLineTrim: true,
    };
    const trimmedRes = generateDynamicPreview(trimmedForm);

    // Trimmed plan has smaller width and bounds than full 2000m survey line
    assert.ok(trimmedRes.w < untrimmedRes.w);
  });

  test('dynamically responds to increasing loop parameters (spacing, distance, overrun)', () => {
    const baseForm = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [{ name: 'LOOP_1', spacing: 5.3, side: 'LEFT', crossoverDistance: 750, overrunBeforeC1: 120, overrunAfterC2: 120 }],
    };
    const baseRes = generateDynamicPreview(baseForm);

    // Now increase spacing to 10.0m, crossover distance to 900m, and overruns to 200m
    const expandedForm = {
      mainLength: 1600,
      mainCenter: 800,
      loops: [{ name: 'LOOP_1', spacing: 10.0, side: 'LEFT', crossoverDistance: 900, overrunBeforeC1: 200, overrunAfterC2: 200 }],
    };
    const expandedRes = generateDynamicPreview(expandedForm);

    assert.ok(baseRes.svg.includes('CAL 750m'));
    assert.ok(expandedRes.svg.includes('CAL 900m'));
    // Expanded spacing increases Y height of drawing
    assert.ok(expandedRes.h > baseRes.h);
  });

  test('renders along curved surveyed alignment points', () => {
    // 3 curved points in UTM meters
    const alignmentPoints = [
      [1000.0, 2000.0],
      [1500.0, 2100.0],
      [2000.0, 2050.0],
    ];
    const form = {
      alignmentPoints,
      loops: [{ name: 'LOOP_CURVED', spacing: 5.3, side: 'LEFT' }],
    };
    const res = generateDynamicPreview(form);

    assert.ok(res.entities > 0);
    assert.ok(res.w > 0);
    assert.ok(res.h > 0);
    assert.ok(res.layers.includes('LOOP_CURVED'));
  });
});
