import { Button, Icon, Subtitle, Text } from "@tremor/react";
import { Provider } from "./providers";
import Image from "next/image";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { useSession } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";
import ProviderMenu from "./provider-menu";
import { toast } from "react-toastify";
import { installWebhook } from "../../utils/helpers";
import { GlobeAltIcon } from "@heroicons/react/24/outline";

interface Props {
  provider: Provider;
  onClick: () => void;
  onDelete?: (provider: Provider) => void;
}

function InstalledSection(
  onDelete?: () => Promise<void>,
  onInstallWebhook?: () => Promise<void>
) {
  return (
    <div className="flex w-full items-center justify-between">
      <Text color="green" className="ml-2.5 text-xs">
        Connected
      </Text>
      <ProviderMenu onDelete={onDelete} onInstallWebhook={onInstallWebhook} />
    </div>
  );
}

const WebhookIcon = (props: any) => (
  <svg
    width="256px"
    height="256px"
    viewBox="0 -8.5 256 256"
    xmlns="http://www.w3.org/2000/svg"
    xmlnsXlink="http://www.w3.org/1999/xlink"
    preserveAspectRatio="xMidYMid"
    {...props}
  >
    <g>
      <path
        d="M119.540432,100.502743 C108.930124,118.338815 98.7646301,135.611455 88.3876025,152.753617 C85.7226696,157.154315 84.4040417,160.738531 86.5332204,166.333309 C92.4107024,181.787152 84.1193605,196.825836 68.5350381,200.908244 C53.8383677,204.759349 39.5192953,195.099955 36.6032893,179.365384 C34.0194114,165.437749 44.8274148,151.78491 60.1824106,149.608284 C61.4694072,149.424428 62.7821041,149.402681 64.944891,149.240571 C72.469175,136.623655 80.1773157,123.700312 88.3025935,110.073173 C73.611854,95.4654658 64.8677898,78.3885437 66.803227,57.2292132 C68.1712787,42.2715849 74.0527146,29.3462646 84.8033863,18.7517722 C105.393354,-1.53572199 136.805164,-4.82141828 161.048542,10.7510424 C184.333097,25.7086706 194.996783,54.8450075 185.906752,79.7822957 C179.052655,77.9239597 172.151111,76.049808 164.563565,73.9917997 C167.418285,60.1274266 165.306899,47.6765751 155.95591,37.0109123 C149.777932,29.9690049 141.850349,26.2780332 132.835442,24.9178894 C114.764113,22.1877169 97.0209573,33.7983633 91.7563309,51.5355878 C85.7800012,71.6669027 94.8245623,88.1111998 119.540432,100.502743 L119.540432,100.502743 Z"
        fill="#C73A63"
      />
      <path
        d="M149.841194,79.4106285 C157.316054,92.5969067 164.905578,105.982857 172.427885,119.246236 C210.44865,107.483365 239.114472,128.530009 249.398582,151.063322 C261.81978,178.282014 253.328765,210.520191 228.933162,227.312431 C203.893073,244.551464 172.226236,241.605803 150.040866,219.46195 C155.694953,214.729124 161.376716,209.974552 167.44794,204.895759 C189.360489,219.088306 208.525074,218.420096 222.753207,201.614016 C234.885769,187.277151 234.622834,165.900356 222.138374,151.863988 C207.730339,135.66681 188.431321,135.172572 165.103273,150.721309 C155.426087,133.553447 145.58086,116.521995 136.210101,99.2295848 C133.05093,93.4015266 129.561608,90.0209366 122.440622,88.7873178 C110.547271,86.7253555 102.868785,76.5124151 102.408155,65.0698097 C101.955433,53.7537294 108.621719,43.5249733 119.04224,39.5394355 C129.363912,35.5914599 141.476705,38.7783085 148.419765,47.554004 C154.093621,54.7244134 155.896602,62.7943365 152.911402,71.6372484 C152.081082,74.1025091 151.00562,76.4886916 149.841194,79.4106285 L149.841194,79.4106285 Z"
        fill="#4B4B4B"
      />
      <path
        d="M167.706921,187.209935 L121.936499,187.209935 C117.54964,205.253587 108.074103,219.821756 91.7464461,229.085759 C79.0544063,236.285822 65.3738898,238.72736 50.8136292,236.376762 C24.0061432,232.053165 2.08568567,207.920497 0.156179306,180.745298 C-2.02835403,149.962159 19.1309765,122.599149 47.3341915,116.452801 C49.2814904,123.524363 51.2485589,130.663141 53.1958579,137.716911 C27.3195169,150.919004 18.3639187,167.553089 25.6054984,188.352614 C31.9811726,206.657224 50.0900643,216.690262 69.7528413,212.809503 C89.8327554,208.847688 99.9567329,192.160226 98.7211371,165.37844 C117.75722,165.37844 136.809118,165.180745 155.847178,165.475311 C163.280522,165.591951 169.019617,164.820939 174.620326,158.267339 C183.840836,147.48306 200.811003,148.455721 210.741239,158.640984 C220.88894,169.049642 220.402609,185.79839 209.663799,195.768166 C199.302587,205.38802 182.933414,204.874012 173.240413,194.508846 C171.247644,192.37176 169.677943,189.835329 167.706921,187.209935 L167.706921,187.209935 Z"
        fill="#4A4A4A"
      />
    </g>
  </svg>
);

export default function ProviderTile({ provider, onClick, onDelete }: Props) {
  const { data: session, status, update } = useSession();

  async function deleteProvider() {
    if (confirm("Are you sure you want to delete this provider?")) {
      const response = await fetch(
        `${getApiURL()}/providers/${provider.type}/${provider.id}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session?.accessToken!}`,
          },
        }
      );
      if (response.ok) {
        onDelete!(provider);
      } else {
        toast.error(`Failed to delete ${provider.type} 😢`);
      }
    }
  }

  const callInstallWebhook = async () =>
    installWebhook(provider, session?.accessToken!);
  return (
    <div
      className={`relative group flex flex-col justify-around items-center bg-white rounded-md shadow-md w-44 h-44 m-2.5 hover:shadow-xl hover:grayscale-0`}
      onClick={onClick}
    >
      {provider.can_setup_webhook && !provider.installed && (
        <Icon
          icon={WebhookIcon}
          className="absolute top-[-15px] right-[-15px]"
          color="green"
          size="sm"
          tooltip="Webhook available"
        />
      )}
      {provider.installed ? (
        InstalledSection(deleteProvider, callInstallWebhook)
      ) : (
        <div></div>
      )}
      <Image
        src={`/icons/${provider.type}-icon.png`}
        width={60}
        height={60}
        alt={provider.type}
        className={`${
          provider.installed ? "grayscale-0" : "grayscale"
        } group-hover:grayscale-0`}
      />
      <div className="h-8">
        <Text
          className={`truncate capitalize ${
            provider.installed ? "" : "group-hover:hidden"
          } ${provider.details?.name ? "w-[100px]" : ""}`}
          title={provider.installed ? provider.details.name : ""}
        >
          {provider.type}{" "}
          {provider.details.name && `(${provider.details.name})`}
        </Text>
        {!provider.installed && (
          <Button
            variant="secondary"
            size="xs"
            color="green"
            className="hidden group-hover:block"
          >
            Connect
          </Button>
        )}
        {/* {provider.installed && (
          <Button
            variant="secondary"
            size="xs"
            color="red"
            className="hidden group-hover:block"
            onClick={deleteProvider}
          >
            Delete
          </Button>
        )} */}
      </div>
    </div>
  );
}
