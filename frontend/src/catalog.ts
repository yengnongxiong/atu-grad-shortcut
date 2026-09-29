/** The ATU catalog's entry for a course (its search puts the course itself first). */
export const catalogUrl = (code: string): string => `https://catalog.atu.edu/search/?P=${encodeURIComponent(code)}`
