export function check(name) {
  const a = flagsmith.hasFeature(name);
  const b = flagsmith.hasFeature(`flag_${name}`);
  return a && b;
}