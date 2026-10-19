/** The UI is fully client-side, so it is exported as static files that the FastAPI backend serves. */
const config = {
  output: 'export',
  images: { unoptimized: true },
};

export default config;
