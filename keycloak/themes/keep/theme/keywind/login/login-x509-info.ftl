<#import "template.ftl" as layout>
<#import "components/atoms/button.ftl" as button>
<#import "components/atoms/button-group.ftl" as buttonGroup>
<#import "components/atoms/form.ftl" as form>
<#import "components/atoms/link.ftl" as link>

<@layout.registrationLayout; section>
  <#if section = "header">
    ${msg("doLogIn")}
  <#elseif section = "form">
    <div>
      <div>${msg("clientCertificate")}</div>
      <div class="text-secondary-600">
        <#if x509.formData.subjectDN??>
          ${(x509.formData.subjectDN!"")}
        <#else>
          ${msg("noCertificate")}
        </#if>
      </div>
    </div>
    <#if x509.formData.isUserEnabled??>
      <div>
        <span>${msg("doX509Login")}</span>
        <b>${(x509.formData.username!'')}</b>
      </div>
    </#if>
    <@form.kw action=url.loginAction method="post">
      <@buttonGroup.kw>
        <@button.kw color="primary" name="login" type="submit">
          ${msg("doContinue")}
        </@button.kw>
        <#if x509.formData.isUserEnabled??>
          <@button.kw color="secondary" name="cancel" type="submit">
            ${msg("doIgnore")}
          </@button.kw>
        </#if>
      </@buttonGroup.kw>
    </@form.kw>
  </#if>
</@layout.registrationLayout>
