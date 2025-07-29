import { render, screen } from '@testing-library/react';
import App from './App';

test('renders subtitle editor heading', () => {
  render(<App />);
  const heading = screen.getByText(/subtitle editor/i);
  expect(heading).toBeInTheDocument();
});
