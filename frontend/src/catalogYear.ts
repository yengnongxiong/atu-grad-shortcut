/**
 * The catalog year a first term falls in. ATU's academic year runs fall, winter intersession
 * (Dec–Jan), spring, summer, so 2026WI belongs to 2026–27 and 2026SU to 2025–26.
 */
export function catalogYearFor(termId: string): string {
  const year = Number(termId.slice(0, 4))
  const season = termId.slice(4)
  const start = season === 'FA' || season === 'WI' ? year : year - 1
  return `${start}-${String((start + 1) % 100).padStart(2, '0')}`
}

type Versioned = { id: string; catalog_year: string; major_key?: string }

const majorOf = (p: Versioned) => p.major_key || p.id

/** Every catalog year's version of the major `programId` belongs to, newest first. */
export function versionsOf<T extends Versioned>(programs: T[], programId: string): T[] {
  const current = programs.find((p) => p.id === programId)
  if (!current) return []
  return programs.filter((p) => majorOf(p) === majorOf(current)).sort((a, b) => b.catalog_year.localeCompare(a.catalog_year))
}

/** The same major's program id in `year`, or `programId` itself when that year has no map. */
export function versionFor<T extends Versioned>(programs: T[], programId: string, year: string): string {
  return versionsOf(programs, programId).find((p) => p.catalog_year === year)?.id ?? programId
}

/** One program per major (in first-seen order): the `preferredYear` version if any, else the newest. */
export function onePerMajor<T extends Versioned>(programs: T[], preferredYear?: string): T[] {
  const chosen = new Map<string, T>()
  for (const p of programs) {
    const key = majorOf(p)
    const held = chosen.get(key)
    const better =
      !held ||
      (preferredYear ? p.catalog_year === preferredYear && held.catalog_year !== preferredYear : false) ||
      (held.catalog_year !== preferredYear && p.catalog_year > held.catalog_year)
    if (better) chosen.set(key, p)
  }
  const order = new Map<string, number>()
  programs.forEach((p, i) => order.has(majorOf(p)) || order.set(majorOf(p), i))
  return [...chosen.values()].sort((a, b) => (order.get(majorOf(a)) ?? 0) - (order.get(majorOf(b)) ?? 0))
}
