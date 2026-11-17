# Third-party notices

## Cloudflare cloudflared

FinalSSH bundles the official Windows AMD64 `cloudflared` executable from the
[Cloudflare cloudflared project](https://github.com/cloudflare/cloudflared).
The release pipeline selects the latest published release and verifies the
binary's SHA256 digest against the digest supplied by the GitHub Releases API
before embedding it in `FinalSSH.exe`.

Cloudflare publishes the cloudflared license as Apache License 2.0 and includes
a Runtime Library Exception. See the
[official Cloudflare license notice](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/license/)
and the [cloudflared releases](https://github.com/cloudflare/cloudflared/releases).

FinalSSH does not modify the cloudflared executable. It invokes it as the
client-side transport required for Cloudflare Access SSH.
