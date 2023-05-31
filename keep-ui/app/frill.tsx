import Script from "next/script";

export default function Frill() {
  return (
    <>
      <Script
        src="https://widget.frill.co/v2/widget.js"
        strategy="lazyOnload"
      ></Script>
      <Script id="frill">
        {`
        window.Frill_Config = window.Frill_Config || [];
        window.Frill_Config.push({ key: 'd858df67-2dda-4f00-9f5f-dcdb62fb5444' });
        `}
      </Script>
    </>
  );
}
