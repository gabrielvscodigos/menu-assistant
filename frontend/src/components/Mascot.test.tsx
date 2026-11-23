import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Mascot } from './Mascot'

describe('Mascot', () => {
  it('shows the avatar with its accessible name', () => {
    render(<Mascot label="The waiter" size={64} />)

    const waiter = screen.getByRole('img', { name: 'The waiter' })
    expect(waiter).toHaveAttribute('data-variant', 'bust')
    expect(waiter).toHaveAttribute('width', '64')
    expect(waiter).toHaveAttribute('height', '64')
  })

  it('shows the full figure with the artwork proportions', () => {
    render(<Mascot variant="full" size={200} label="The waiter" />)

    const waiter = screen.getByRole('img', { name: 'The waiter' })
    expect(waiter).toHaveAttribute('data-variant', 'full')
    expect(waiter).toHaveAttribute('width', '250') // 600 x 480 artwork
  })

  it('hides a copy without a label from screen readers', () => {
    const { container } = render(<Mascot size={36} />)

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(container.querySelector('img')).toHaveAttribute('aria-hidden', 'true')
  })
})
