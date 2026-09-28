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
