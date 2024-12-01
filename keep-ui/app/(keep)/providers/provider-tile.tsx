import {
  Badge,
  Icon,
  SparkAreaChart,
  Subtitle,
  Text,
  Title,
} from "@tremor/react";
import { Provider, TProviderLabels } from "./providers";
import {
  BellAlertIcon,
  ChatBubbleBottomCenterIcon,
  CircleStackIcon,
  ExclamationTriangleIcon,
  QueueListIcon,
  TicketIcon,
  MapIcon,
  Cog6ToothIcon,
} from "@heroicons/react/20/solid";
import "./provider-tile.css";
import moment from "moment";
import ImageWithFallback from "@/components/ImageWithFallback";
import { FaCode } from "react-icons/fa";

interface Props {
  provider: Provider;
  onClick: () => void;
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

const OAuthIcon = (props: any) => (
  <svg
    width="800px"
    height="800px"
    viewBox="-10 -5 1034 1034"
    xmlns="http://www.w3.org/2000/svg"
    xmlnsXlink="http://www.w3.org/1999/xlink"
    {...props}
  >
    <path
      fill="orange"
      d="M504 228q-16 0 -33 1q-33 2 -70 11q-35 9 -60 20q-38 17 -77 44q-44 31 -78 75t-55 96l-5 12q-9 22 -12 33q-13 45 -13 98q0 49 9 93q22 100 82 171q52 62 139 108q48 25 109.5 33.5t124.5 -1t115 -35.5q90 -46 152 -139q31 -46 48 -100q19 -60 19 -124q0 -57 -21 -119 q-17 -52 -46 -97q-51 -81 -128 -127q-88 -53 -200 -53zM470 418h54q16 0 29 9.5t18 24.5l106 320q7 20 -2.5 38.5t-28.5 24.5q-8 2 -16 2q-16 0 -29 -9t-18 -25l-23 -73h-120l-23 73q-5 15 -18 24.5t-29 9.5q-8 0 -15 -2q-20 -6 -29.5 -24t-3.5 -38l101 -320q5 -16 18 -25.5 t29 -9.5z"
    />
  </svg>
);

// add +1 to each distribution to avoid 0 values
const addOneToDistribution = (distribution: any[]) => {
  let dist = distribution.map((data) => ({
    ...data,
    number: data.number + 1,
  }));
  return dist;
};

const getEmptyDistribution = () => {
  let emptyDistribution = [];
  for (let i = 0; i < 24; i++) {
    emptyDistribution.push({
      hour: i.toString(),
      number: 0.2,
    });
  }
  return emptyDistribution;
};

function getIconForTag(tag: TProviderLabels) {
  switch (tag) {
    case "alert":
      return BellAlertIcon;
    case "data":
      return CircleStackIcon;
    case "ticketing":
      return TicketIcon;
    case "queue":
      return QueueListIcon;
    case "topology":
      return MapIcon;
    case "incident":
      return ExclamationTriangleIcon;
    default:
      return ChatBubbleBottomCenterIcon;
  }
}

export default function ProviderTile({ provider, onClick }: Props) {
  const renderTags = () => {
    if (provider.installed || provider.linked) {
      return null;
    }
    return (
      <div className="labels flex flex-wrap gap-1">
        {provider.tags.map((tag) => {
          return (
            <Badge key={tag} icon={getIconForTag(tag)} size="xs" color="slate">
              <p>{tag}</p>
            </Badge>
          );
        })}
      </div>
    );
  };

  const renderChart = () => {
    const className = "mt-2 h-8 w-20 sm:h-10 sm:w-full";
    if (!provider.installed && !provider.linked) {
      return null;
    }

    if (provider.alertsDistribution && provider.alertsDistribution.length > 0) {
      return (
        <SparkAreaChart
          data={addOneToDistribution(provider.alertsDistribution)}
          categories={["number"]}
          index={"hour"}
          colors={["orange"]}
          showGradient={true}
          autoMinValue={true}
          className={className}
        />
      );
    }

    return (
      <SparkAreaChart
        data={getEmptyDistribution()}
        categories={["number"]}
        index={"hour"}
        colors={["orange"]}
        className={className}
        autoMinValue={true}
        maxValue={1}
      />
    );
  };
  return (
    <button
      className={
        "min-h-36 tile-basis text-left min-w-0 py-4 px-4 relative group flex justify-around items-center bg-white rounded-lg shadow hover:grayscale-0 gap-3" +
        // Add fixed height only if provider card doesn't have much content
        (!provider.installed && !provider.linked ? " h-32" : "") +
        (!provider.linked
          ? " cursor-pointer hover:shadow-lg"
          : " cursor-auto") +
        (provider.coming_soon && !provider.linked
          ? " opacity-50 cursor-not-allowed"
          : "")
      }
      onClick={provider.coming_soon ? undefined : onClick}
      disabled={provider.coming_soon}
    >
      <div className="flex-1 min-w-0">
        {(provider.can_setup_webhook || provider.supports_webhook) &&
          !provider.installed &&
          !provider.linked && (
            <Icon
              icon={WebhookIcon}
              className="absolute top-[-15px] right-[-15px] grayscale hover:grayscale-0 group-hover:grayscale-0"
              color="green"
              size="sm"
              tooltip="Webhook available"
            />
          )}
        {provider.oauth2_url && !provider.installed && !provider.linked && (
          <Icon
            icon={OAuthIcon}
            className={`absolute top-[-15px] ${
              provider.can_setup_webhook || provider.supports_webhook
                ? "right-[-0px]"
                : "right-[-15px]"
            } grayscale hover:grayscale-0 group-hover:grayscale-0`}
            color="green"
            size="sm"
            tooltip="OAuth2 available"
          />
        )}
        {provider.installed ? (
          <Text color={"green"} className="flex text-xs">
            Connected
          </Text>
        ) : null}
        {provider.linked ? (
          <Text color={"green"} className="flex text-xs">
            Linked
          </Text>
        ) : null}
        {provider.provisioned ? (
          <Icon
            icon={FaCode}
            className="absolute top-[-15px] right-[-15px]"
            color="orange"
            size="sm"
            tooltip="Provisioned"
          />
        ) : null}
        <div className="flex flex-col gap-2">
          <div>
            <Title className="capitalize" title={provider.details?.name}>
              {provider.display_name}{" "}
              {provider.coming_soon && !provider.linked && (
                <span className="text-sm">(Coming Soon)</span>
              )}
            </Title>

            {provider.details && provider.details.name && (
              <Subtitle className="truncate">
                id: {provider.details.name}
              </Subtitle>
            )}
            {provider.last_alert_received ? (
              <Text>
                Last alert: {moment(provider.last_alert_received).fromNow()}
              </Text>
            ) : (
              <p></p>
            )}
            {provider.linked && provider.id ? (
              <Text className="truncate">Id: {provider.id}</Text>
            ) : null}
            {renderChart()}
          </div>
          {renderTags()}
        </div>
      </div>
      <div className="flex flex-col justify-center h-full">
        <div className="flex-grow flex items-center">
          <ImageWithFallback
            src={`/icons/${provider.type}-icon.png`}
            fallbackSrc={`/icons/keep-icon.png`}
            width={48}
            height={48}
            alt={provider.type}
            className={`${
              provider.installed || provider.linked || provider.coming_soon
                ? ""
                : "grayscale group-hover:grayscale-0"
            }`}
          />
        </div>
        {provider.installed ? (
          <Icon
            icon={Cog6ToothIcon}
            color="gray"
            className="w-6 h-6 self-end place-self-end"
            tooltip="Modify"
          />
        ) : null}
      </div>
    </button>
  );
}
