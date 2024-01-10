# wlb-cf-ddns

## What is it?

`wlb-cf-ddns` is a dynamic DNS script that works in conjunction with the VyOS WAN load balancer and the Cloudflare DNS API.

## Features

- Automatically adds new DNS A records under a defined subdomain for defined load-balanced WAN interfaces.
- Updates existing DNS A records for defined load-balanced WAN interfaces when they become active.
- Deletes existing DNS A records for defined load-balanced WAN interfaces when they fail.
- Uses an external IPv4 address API to detect the true external IPv4 address for each WAN interface.

## How do I use it?

1. Populate the `configurables` section in `wlb-cf-ddns.py` with the relevant values:

	- `zone_name`: the DNS zone name, e.g. `example.com`
	- `record_name`: the zone sub-domain that you want the dynamic A records under, e.g. `wan.example.com`
	- `interfaces`: a list of your WAN interfaces
	- `api_token`: your Cloudflare API token, which should have the following permissions for the relevant zone:
		- `Zone:Read`
		- `DNS:Read`
		- `DNS:Edit`

2. Copy the `wlb-cf-ddns` and `wlb-cf-ddns.py` files to the `/config/scripts/` directory on your VyOS router.
3. Make the files executable:

	```shell
	chmod +x /config/scripts/wlb-cf-ddns*
	```

4. Configure the VyOS WAN load balancer with a hook:

	```shell
	set load-balancing wan hook /config/scripts/wlb-cf-ddns
	```
