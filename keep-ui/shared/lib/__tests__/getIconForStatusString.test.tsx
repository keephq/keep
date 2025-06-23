import React from 'react';
import { render } from '@testing-library/react';
import { getIconForStatusString } from '../../ui/utils/getIconForStatusString';
import {
  CheckCircleIcon,
  NoSymbolIcon,
  XCircleIcon,
} from "@heroicons/react/20/solid";

// Mock the HeroIcons
jest.mock('@heroicons/react/20/solid', () => ({
  CheckCircleIcon: (props: any) => <div data-testid="CheckCircleIcon" {...props} />,
  NoSymbolIcon: (props: any) => <div data-testid="NoSymbolIcon" {...props} />,
  XCircleIcon: (props: any) => <div data-testid="XCircleIcon" {...props} />,
}));

describe('getIconForStatusString', () => {
  it('should return a CheckCircleIcon for "success" status', () => {
    const { getByTestId } = render(<>{getIconForStatusString('success')}</>);
    expect(getByTestId('CheckCircleIcon')).toBeInTheDocument();
    expect(getByTestId('CheckCircleIcon')).toHaveClass('text-green-500');
  });

  it('should return a NoSymbolIcon for "skipped" status', () => {
    const { getByTestId } = render(<>{getIconForStatusString('skipped')}</>);
    expect(getByTestId('NoSymbolIcon')).toBeInTheDocument();
    expect(getByTestId('NoSymbolIcon')).toHaveClass('text-slate-500');
  });

  it('should return a XCircleIcon for "failed" status', () => {
    const { getByTestId } = render(<>{getIconForStatusString('failed')}</>);
    expect(getByTestId('XCircleIcon')).toBeInTheDocument();
    expect(getByTestId('XCircleIcon')).toHaveClass('text-red-500');
  });

  it('should return a XCircleIcon for "fail" status', () => {
    const { getByTestId } = render(<>{getIconForStatusString('fail')}</>);
    expect(getByTestId('XCircleIcon')).toBeInTheDocument();
    expect(getByTestId('XCircleIcon')).toHaveClass('text-red-500');
  });

  it('should return a XCircleIcon for "failure" status', () => {
    const { getByTestId } = render(<>{getIconForStatusString('failure')}</>);
    expect(getByTestId('XCircleIcon')).toBeInTheDocument();
    expect(getByTestId('XCircleIcon')).toHaveClass('text-red-500');
  });

  it('should return a XCircleIcon for "error" status', () => {
    const { getByTestId } = render(<>{getIconForStatusString('error')}</>);
    expect(getByTestId('XCircleIcon')).toBeInTheDocument();
    expect(getByTestId('XCircleIcon')).toHaveClass('text-red-500');
  });

  it('should return a XCircleIcon for "timeout" status', () => {
    const { getByTestId } = render(<>{getIconForStatusString('timeout')}</>);
    expect(getByTestId('XCircleIcon')).toBeInTheDocument();
    expect(getByTestId('XCircleIcon')).toHaveClass('text-red-500');
  });

  it('should return a loader element for "in_progress" status', () => {
    const { container } = render(<>{getIconForStatusString('in_progress')}</>);
    expect(container.querySelector('.loader')).toBeInTheDocument();
  });

  it('should return a loader element for unknown status', () => {
    const { container } = render(<>{getIconForStatusString('unknown')}</>);
    expect(container.querySelector('.loader')).toBeInTheDocument();
  });
});