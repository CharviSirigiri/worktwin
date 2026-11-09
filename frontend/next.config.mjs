/** Static export: the build in ./out is plain HTML/JS, hosted on Firebase Hosting. */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
