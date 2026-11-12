# Security policy

## Supported versions
Security fixes go into the latest release of Cue Media Engine. Please update before reporting.

## Reporting a vulnerability
Please **do not open a public issue** for a security problem.

Use GitHub's private report: on the repository page choose **Security**, then **Report a vulnerability**
(https://github.com/L252-Media-Production/cue-media-engine/security/advisories/new).

Include the version, how it is installed, what you found and how to reproduce it. You can expect an answer within about a week; this is a small project run by one company, so please be patient.

## Scope and expectations
The web page and the HTTP and OSC control have **no authentication by design**. They are meant for a trusted network behind a firewall or a reverse proxy that adds authentication. Exposing port 8080 or 9000 to the internet is a setup problem, not a vulnerability. Reports about what an attacker can do from outside that assumption (for example a way to read or write files outside the media folders, or to run commands) are welcome.
