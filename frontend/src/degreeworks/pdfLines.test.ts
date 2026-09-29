import { groupTextItems } from './pdfLines'

it('joins text on one baseline left to right and starts a new line below', () => {
  const items = [
    { str: 'COMPOSITION I', x: 200, y: 700 },
    { str: 'ENGL 1013', x: 120, y: 700.8 },
    { str: 'CE', x: 400, y: 699.5 },
    { str: '2024', x: 450, y: 688 },
    { str: '  ', x: 10, y: 650 },
  ]
  expect(groupTextItems(items)).toEqual(['ENGL 1013 COMPOSITION I CE', '2024'])
})
