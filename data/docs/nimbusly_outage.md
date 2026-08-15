# Nimbusly Suffers Multi-Region Outage After Config Rollout

Nimbusly, the cloud infrastructure provider, experienced a six-hour outage
across its US-East and EU-West regions after a misconfigured routing
update was pushed to production without a canary rollout. Customer
dashboards were unreachable and several downstream SaaS companies that
depend on Nimbusly's object storage reported cascading failures.

The company's engineering lead said the incident review would focus on
why the change bypassed staged rollout checks, and that a postmortem
would be published within two weeks. This is the second major incident
for Nimbusly in the past year, following a similar but shorter outage
tied to a certificate expiry.
