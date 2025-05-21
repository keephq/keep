import { getStatusIcon, getStatusColor } from '../status-utils';
import {
  ExclamationCircleIcon,
  CheckCircleIcon,
  CircleStackIcon,
  PauseIcon,
} from "@heroicons/react/24/outline";
import { IoIosGitPullRequest } from "react-icons/io";

describe('status-utils', () => {
  describe('getStatusIcon', () => {
    it('should return ExclamationCircleIcon for "firing" status', () => {
      expect(getStatusIcon('firing')).toBe(ExclamationCircleIcon);
    });

    it('should return CheckCircleIcon for "resolved" status', () => {
      expect(getStatusIcon('resolved')).toBe(CheckCircleIcon);
    });

    it('should return PauseIcon for "acknowledged" status', () => {
      expect(getStatusIcon('acknowledged')).toBe(PauseIcon);
    });

    it('should return IoIosGitPullRequest for "merged" status', () => {
      expect(getStatusIcon('merged')).toBe(IoIosGitPullRequest);
    });

    it('should return CircleStackIcon for unknown status', () => {
      expect(getStatusIcon('unknown')).toBe(CircleStackIcon);
    });

    it('should be case insensitive', () => {
      expect(getStatusIcon('FIRING')).toBe(ExclamationCircleIcon);
      expect(getStatusIcon('Resolved')).toBe(CheckCircleIcon);
      expect(getStatusIcon('aCkNoWlEdGeD')).toBe(PauseIcon);
    });
  });

  describe('getStatusColor', () => {
    it('should return "red" for "firing" status', () => {
      expect(getStatusColor('firing')).toBe('red');
    });

    it('should return "green" for "resolved" status', () => {
      expect(getStatusColor('resolved')).toBe('green');
    });

    it('should return "gray" for "acknowledged" status', () => {
      expect(getStatusColor('acknowledged')).toBe('gray');
    });

    it('should return "purple" for "merged" status', () => {
      expect(getStatusColor('merged')).toBe('purple');
    });

    it('should return "gray" for unknown status', () => {
      expect(getStatusColor('unknown')).toBe('gray');
    });

    it('should be case insensitive', () => {
      expect(getStatusColor('FIRING')).toBe('red');
      expect(getStatusColor('Resolved')).toBe('green');
      expect(getStatusColor('aCkNoWlEdGeD')).toBe('gray');
    });
  });
});