Generate a KQL query related to Trivy compromise to identify IOC that matches the following criteria:

Network indicators:

IP addresses:
- 45.148.10.212

Domains:
- scan.aquasecurtiy.org
- tdtqy-oyaaa-aaaae-af2dq-cai.raw.icp0.io
- plug-tab-protective-relay.trycloudflare.com

Hash indicators:

SHA256 hashes:
- 0880819ef821cff918960a39c1c1aada55a5593c61c608ea9215da858a86e349

Here is an example of how to use union operator to combine multiple queries for different indicators:

```kql
// Using union isfuzzy=true to access non-existing view:                                     
let View_1 = view () { print x=1 };
let View_2 = view () { print x=1 };
union isfuzzy=true
(View_1 | where x > 0), 
(View_2 | where x > 0)
```

The query should not include empty lines.