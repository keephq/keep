// File: keep/providers/snmp-prov/snmp-prov.test.ts
import { sendSnmpTraps } from './snmp-prov';
import { Provider } from '@/shared/api/providers';

describe('snmp-prov', () => {
  describe('sendSnmpTraps', () => {
    it('should send SNMP traps as Keep alerts', async () => {
      const provider = {
        type: 'snmp',
        config: {
          community: 'public',
          host: 'localhost',
          port: 161
        }
      };
      const providers: Provider[] = [provider];

      await expect(sendSnmpTraps(providers)).resolves.not.toThrow();
    });
  });
});