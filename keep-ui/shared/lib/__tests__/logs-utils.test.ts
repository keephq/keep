import { getLogLineStatus, getStepStatus } from '../logs-utils';
import { LogEntry } from '@/shared/api/workflow-executions';

describe('logs-utils', () => {
  describe('getLogLineStatus', () => {
    it('should return "failed" for logs containing "Failed to"', () => {
      const log: LogEntry = {
        timestamp: '2023-01-01T00:00:00Z',
        message: 'Failed to execute step',
        context: {}
      };
      expect(getLogLineStatus(log)).toBe('failed');
    });

    it('should return "failed" for logs containing "Error"', () => {
      const log: LogEntry = {
        timestamp: '2023-01-01T00:00:00Z',
        message: 'Error occurred during execution',
        context: {}
      };
      expect(getLogLineStatus(log)).toBe('failed');
    });

    it('should return "success" for logs containing "ran successfully" for Action', () => {
      const log: LogEntry = {
        timestamp: '2023-01-01T00:00:00Z',
        message: 'Action sendEmail ran successfully',
        context: {}
      };
      expect(getLogLineStatus(log)).toBe('success');
    });

    it('should return "success" for logs containing "ran successfully" for Step', () => {
      const log: LogEntry = {
        timestamp: '2023-01-01T00:00:00Z',
        message: 'Step processData ran successfully',
        context: {}
      };
      expect(getLogLineStatus(log)).toBe('success');
    });

    it('should not return "success" for logs containing "Steps ran successfully"', () => {
      const log: LogEntry = {
        timestamp: '2023-01-01T00:00:00Z',
        message: 'Steps ran successfully',
        context: {}
      };
      expect(getLogLineStatus(log)).not.toBe('success');
    });

    it('should return "skipped" for logs containing "evaluated NOT to run"', () => {
      const log: LogEntry = {
        timestamp: '2023-01-01T00:00:00Z',
        message: 'Step cleanupData evaluated NOT to run',
        context: {}
      };
      expect(getLogLineStatus(log)).toBe('skipped');
    });

    it('should return null for logs that do not match any pattern', () => {
      const log: LogEntry = {
        timestamp: '2023-01-01T00:00:00Z',
        message: 'Normal log message',
        context: {}
      };
      expect(getLogLineStatus(log)).toBe(null);
    });

    it('should handle undefined message gracefully', () => {
      const log: LogEntry = {
        timestamp: '2023-01-01T00:00:00Z',
        message: undefined,
        context: {}
      };
      expect(getLogLineStatus(log)).toBe(null);
    });
  });

  describe('getStepStatus', () => {
    it('should return "success" if a success log exists', () => {
      const logs: LogEntry[] = [
        {
          timestamp: '2023-01-01T00:00:00Z',
          message: 'Step processData ran successfully',
          context: {}
        }
      ];
      expect(getStepStatus('processData', false, logs)).toBe('success');
    });

    it('should return "success" for action if a success log exists', () => {
      const logs: LogEntry[] = [
        {
          timestamp: '2023-01-01T00:00:00Z',
          message: 'Action sendEmail ran successfully',
          context: {}
        }
      ];
      expect(getStepStatus('sendEmail', true, logs)).toBe('success');
    });

    it('should return "failed" if a failure log exists', () => {
      const logs: LogEntry[] = [
        {
          timestamp: '2023-01-01T00:00:00Z',
          message: 'Failed to run step processData',
          context: {}
        }
      ];
      expect(getStepStatus('processData', false, logs)).toBe('failed');
    });

    it('should return "failed" for action if a failure log exists', () => {
      const logs: LogEntry[] = [
        {
          timestamp: '2023-01-01T00:00:00Z',
          message: 'Failed to run action sendEmail',
          context: {}
        }
      ];
      expect(getStepStatus('sendEmail', true, logs)).toBe('failed');
    });

    it('should return "skipped" if a skip log exists', () => {
      const logs: LogEntry[] = [
        {
          timestamp: '2023-01-01T00:00:00Z',
          message: 'Step cleanupData evaluated NOT to run',
          context: {}
        }
      ];
      expect(getStepStatus('cleanupData', false, logs)).toBe('skipped');
    });

    it('should return "pending" if no status logs exist', () => {
      const logs: LogEntry[] = [
        {
          timestamp: '2023-01-01T00:00:00Z',
          message: 'Some unrelated log',
          context: {}
        }
      ];
      expect(getStepStatus('processData', false, logs)).toBe('pending');
    });

    it('should return "pending" for empty logs array', () => {
      expect(getStepStatus('processData', false, [])).toBe('pending');
    });

    it('should return "pending" if logs is undefined', () => {
      // @ts-ignore - Intentionally passing undefined to test handling
      expect(getStepStatus('processData', false, undefined)).toBe('pending');
    });

    it('should prioritize success over failure if both logs exist', () => {
      const logs: LogEntry[] = [
        {
          timestamp: '2023-01-01T00:00:00Z',
          message: 'Failed to run step processData',
          context: {}
        },
        {
          timestamp: '2023-01-01T00:00:01Z',
          message: 'Step processData ran successfully',
          context: {}
        }
      ];
      expect(getStepStatus('processData', false, logs)).toBe('success');
    });

    it('should prioritize failure over skipped if both logs exist', () => {
      const logs: LogEntry[] = [
        {
          timestamp: '2023-01-01T00:00:00Z',
          message: 'Step processData evaluated NOT to run',
          context: {}
        },
        {
          timestamp: '2023-01-01T00:00:01Z',
          message: 'Failed to run step processData',
          context: {}
        }
      ];
      expect(getStepStatus('processData', false, logs)).toBe('failed');
    });
  });
});