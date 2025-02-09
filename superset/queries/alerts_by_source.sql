select count(*) as c, provider_type
from alert
group by provider_type
