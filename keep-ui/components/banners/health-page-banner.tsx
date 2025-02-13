"use client";
import React from "react";
import KeepBanner from "@/components/banners/BannerBase";

const HealthPageBanner = () => {
  return <KeepBanner
    bannerId="health-page-banner"
    text={<span>
      Easily check the configuration quality of your observability tools without the need to sign up.
      <br />Your credentials will not be stored at any point.
    </span>}
    newWindow={false}
  />
};

export default HealthPageBanner;
