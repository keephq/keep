import {Provider} from './provider-row';


// TODO - this should be fetched from the backend
const Providers: Provider[] = [
    {
      id: 'grafana',
      name: 'Grafana',
      // TODO: 'host' and 'token' should match the names of the fields in the backend
      //        so it should be generic
      authentication: [
        { name: 'token', desc: 'Grafana Service Account', type: 'string' , placeholder: 'glsa_1234567890', validation: (value: string) => value.startsWith('glsa')},
        { name: 'host', desc: 'Grafana hostname', type: 'string', placeholder: 'https://keephq.grafana.net', validation: (value: string) => value.startsWith('https') && value.endsWith('grafana.net'),
      },
      ],
      icon: '/grafana.svg',
      connected: false,
    },
    {
      id: 'datadog',
      name: 'Datadog',
      authentication: [
        { name: 'api_key', desc: 'Datadog API key', type: 'string', placeholder: '1234567890abcdef1234567890abcdef' },
        { name: 'app_key', desc: 'Datadog App key', type: 'string', placeholder: '1234567890abcdef1234567890abcdef' },
        { name: 'hostname', desc: 'Datadog hostname', type: 'string', placeholder: 'https://us1.datadog.com', required: false },
      ],
      icon: '/datadog.svg',
      connected: false,
    },
  ];

  export default Providers;
