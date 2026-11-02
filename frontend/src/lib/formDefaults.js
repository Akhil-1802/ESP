/**
 * Consolidated blank state factories for form items.
 */

export const blankLoop = () => ({
  name: '',
  side: 'LEFT',
  spacing: '',
  c1: '',
  c2: '',
  turnout: '',
  turnoutVariant: '',
  crossoverDistance: '',
  extStart: '',
  extEnd: '',
  referenceTrack: 'MAIN_LINE',
});

export const blankLine = () => ({
  name: '',
  spacing: '',
  side: 'LEFT',
});

export const blankMainLine = (referenceTrack = 'MAIN_LINE') => ({
  referenceTrack,
  spacing: '',
  side: 'LEFT',
  direction: 'DN',
});

export const blankCrossover = () => ({
  from: '',
  to: '',
  chainage: '',
  direction: 'FORWARD',
  turnout: '',
  autoAnchor: '',
});

export const blankStation = () => ({
  platform: '',
  length: '',
  width: '',
  side: 'RIGHT',
  name: '',
  chainage: '',
});

export const blankFob = () => ({
  refTrack: 'MAIN_LINE',
  chainage: '',
  platforms: [],
  width: '',
  extStart: '',
  extEnd: '',
  arms: [],
});

export const blankArm = () => ({
  platform: '',
  length: '',
  side: 'LEFT',
});

export const blankSiding = () => ({
  sourceTrack: 'MAIN_LINE',
  chainage: '',
  direction: 'FORWARD',
  side: 'LEFT',
  turnout: '1:8.5',
  csl: '120',
  spacing: '5.3',
});

export const blankRob = () => ({
  platform: 'PLATFORM_1',
  referenceEnd: 'START',
  offset: '50.0',
  width: '10.0',
  referenceTrack: 'MAIN_LINE',
  blockName: 'SGFD',
});

export const blankGradient = () => ({
  track: 'MAIN_LINE',
  chainage: '',
  direction: 'UP',
  leftValue: '',
  leftDirection: 'STRAIGHT',
  rightValue: '',
  rightDirection: 'RISE',
  rl: '',
});



