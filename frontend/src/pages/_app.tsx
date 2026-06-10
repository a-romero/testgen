import type { AppProps } from "next/app";
import Head from "next/head";
import "../styles/globals.css";
import AppLayout from "../components/Layout";
import { ProjectProvider } from "../lib/project-context";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <title>TestGen — QA Test Case Studio</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <ProjectProvider>
        <AppLayout>
          <Component {...pageProps} />
        </AppLayout>
      </ProjectProvider>
    </>
  );
}
