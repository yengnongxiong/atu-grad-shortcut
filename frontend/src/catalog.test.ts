import { catalogUrl } from './catalog'

it('links a course code to its ATU catalog entry', () => {
  expect(catalogUrl('COMS 1013')).toBe('https://catalog.atu.edu/search/?P=COMS%201013')
})
