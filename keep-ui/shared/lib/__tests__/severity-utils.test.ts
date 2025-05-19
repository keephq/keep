import {
  UISeverity,
  getSeverityBgClassName,
  getSeverityLabelClassName,
  getSeverityTextClassName
} from '../../ui/utils/severity-utils';

describe('severity-utils', () => {
  describe('getSeverityBgClassName', () => {
    it('should return "bg-red-500" for critical severity', () => {
      expect(getSeverityBgClassName(UISeverity.Critical)).toBe('bg-red-500');
    });

    it('should return "bg-orange-500" for high severity', () => {
      expect(getSeverityBgClassName(UISeverity.High)).toBe('bg-orange-500');
    });

    it('should return "bg-orange-500" for error severity', () => {
      expect(getSeverityBgClassName(UISeverity.Error)).toBe('bg-orange-500');
    });

    it('should return "bg-yellow-500" for warning severity', () => {
      expect(getSeverityBgClassName(UISeverity.Warning)).toBe('bg-yellow-500');
    });

    it('should return "bg-blue-500" for info severity', () => {
      expect(getSeverityBgClassName(UISeverity.Info)).toBe('bg-blue-500');
    });

    it('should return "bg-emerald-500" for low severity', () => {
      expect(getSeverityBgClassName(UISeverity.Low)).toBe('bg-emerald-500');
    });

    it('should return "bg-emerald-500" for undefined or unknown severity', () => {
      expect(getSeverityBgClassName(undefined)).toBe('bg-emerald-500');
      expect(getSeverityBgClassName('unknown' as UISeverity)).toBe('bg-emerald-500');
    });
  });

  describe('getSeverityLabelClassName', () => {
    it('should return "bg-red-100" for critical severity', () => {
      expect(getSeverityLabelClassName(UISeverity.Critical)).toBe('bg-red-100');
    });

    it('should return "bg-orange-100" for high severity', () => {
      expect(getSeverityLabelClassName(UISeverity.High)).toBe('bg-orange-100');
    });

    it('should return "bg-orange-100" for error severity', () => {
      expect(getSeverityLabelClassName(UISeverity.Error)).toBe('bg-orange-100');
    });

    it('should return "bg-yellow-100" for warning severity', () => {
      expect(getSeverityLabelClassName(UISeverity.Warning)).toBe('bg-yellow-100');
    });

    it('should return "bg-blue-100" for info severity', () => {
      expect(getSeverityLabelClassName(UISeverity.Info)).toBe('bg-blue-100');
    });

    it('should return "bg-emerald-100" for low severity', () => {
      expect(getSeverityLabelClassName(UISeverity.Low)).toBe('bg-emerald-100');
    });

    it('should return "bg-emerald-100" for undefined or unknown severity', () => {
      expect(getSeverityLabelClassName(undefined)).toBe('bg-emerald-100');
      expect(getSeverityLabelClassName('unknown' as UISeverity)).toBe('bg-emerald-100');
    });
  });

  describe('getSeverityTextClassName', () => {
    it('should return "text-red-500" for critical severity', () => {
      expect(getSeverityTextClassName(UISeverity.Critical)).toBe('text-red-500');
    });

    it('should return "text-orange-500" for high severity', () => {
      expect(getSeverityTextClassName(UISeverity.High)).toBe('text-orange-500');
    });

    it('should return "text-orange-500" for error severity', () => {
      expect(getSeverityTextClassName(UISeverity.Error)).toBe('text-orange-500');
    });

    it('should return "text-amber-900" for warning severity', () => {
      expect(getSeverityTextClassName(UISeverity.Warning)).toBe('text-amber-900');
    });

    it('should return "text-blue-500" for info severity', () => {
      expect(getSeverityTextClassName(UISeverity.Info)).toBe('text-blue-500');
    });

    it('should return "text-emerald-500" for low severity', () => {
      expect(getSeverityTextClassName(UISeverity.Low)).toBe('text-emerald-500');
    });

    it('should return "text-emerald-500" for undefined or unknown severity', () => {
      expect(getSeverityTextClassName(undefined)).toBe('text-emerald-500');
      expect(getSeverityTextClassName('unknown' as UISeverity)).toBe('text-emerald-500');
    });
  });
});