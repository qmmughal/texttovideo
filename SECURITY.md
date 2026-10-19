# Security

## Design

Frame is a single-user application for your own computer. It is not designed to be exposed to a network or shared between users.

- The server listens on `127.0.0.1` only. The Docker setup publishes its port on `127.0.0.1` as well.
- Requests must carry a localhost Host header, and browser requests from other origins are rejected.
- Ollama and ComfyUI addresses must be localhost, or a service name you list in `FRAME_SERVICE_HOSTS`.
- Uploads are limited to known media types, validated, capped at 512 MB, and stored under generated names; asset paths cannot leave the data folder.
- External programs (FFmpeg, PowerShell speech) are started with argument lists, never shell strings, and narration text is passed through a file.
- Network access happens only to your local model servers and to Hugging Face or Ollama when you start a model download.

ComfyUI custom nodes, Ollama models, and downloaded voices or image models are third-party software and data that you choose to install and trust.

## Supported versions

Security fixes are made on the latest release.

## Reporting a vulnerability

Please report privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Include the version, your operating system, and steps to reproduce. Please don't open a public issue for a security problem.
