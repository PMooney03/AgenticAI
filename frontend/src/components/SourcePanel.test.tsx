import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { Source } from '../api/types'
import { SourcePanel } from './SourcePanel'

const sources: Source[] = [
  {
    label: 1,
    document_id: 'd1',
    document_name: 'asb_falcon.pdf',
    page: 2,
    score: 0.7909,
    snippet: 'The main risk is supplier delay.',
    cited: true,
  },
  {
    label: 2,
    document_id: 'd1',
    document_name: 'asb_falcon.pdf',
    page: 3,
    score: 0.7533,
    snippet: 'Project Falcon is led by Dana Whitfield.',
    cited: false,
  },
]

describe('SourcePanel', () => {
  it('renders filename, page, score and cited flag', () => {
    render(<SourcePanel sources={sources} activeLabel={null} onSelect={() => undefined} />)
    expect(screen.getAllByText('asb_falcon.pdf').length).toBeGreaterThan(0)
    expect(screen.getByText('Page 2')).toBeInTheDocument()
    expect(screen.getByText('Score 0.79')).toBeInTheDocument()
    expect(screen.getByText('Cited')).toBeInTheDocument()
    expect(screen.getByText('Retrieved')).toBeInTheDocument()
    expect(screen.queryByText('The main risk is supplier delay.')).not.toBeInTheDocument()
  })

  it('expands the snippet of the active source', async () => {
    const onSelect = vi.fn()
    render(<SourcePanel sources={sources} activeLabel={1} onSelect={onSelect} />)
    expect(screen.getByText('The main risk is supplier delay.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /source 2, page 3/i }))
    expect(onSelect).toHaveBeenCalledWith(2)
  })
})
