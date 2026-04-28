import { Provider } from '@/shared/api/providers';

export function isProviderInstalled(provider: Provider, providers: Provider[]): boolean {
    return providers.includes(provider);
}

export function sendSNMPTrap(trap: { oid: string, value: string }, providers: Provider[]): void {
    const snmpProvider = providers.find(p => p.type === 'snmp');
    if (snmpProvider && snmpProvider.installed) {
        const snmp = require('snmp');
        snmp.send_trap(trap.oid, trap.value);
    } else {
        throw new Error("SNMP provider is not installed or configured");
    }
}