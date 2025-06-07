"use client";

import React, { useState } from "react";

export default function CloneSiteApp() {
  const [url, setUrl] = useState("");
  const [html, setHtml] = useState("");
  const [css, setCss] = useState("");
  const [combinedHtml, setCombinedHtml] = useState("");

  const handleGenerate = async () => {
    const res = await fetch("http://localhost:8000/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url }),
    });

    if (res.ok) {
      const data = await res.json();
      setHtml(data.html);
      setCss(data.css);
      setCombinedHtml(data.combined_html);
    } else {
      alert("Failed to generate clone.");
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#000", // black background
        padding: "2rem",
        color: "white",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <h1 style={{ fontSize: "2rem", marginBottom: "1rem" }}>
        Website Cloner
      </h1>
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Enter website URL..."
          style={{
            flex: 1,
            padding: "0.5rem",
            borderRadius: "5px",
            border: "1px solid #ccc",
          }}
        />
        <button
          onClick={handleGenerate}
          style={{
            padding: "0.5rem 1rem",
            backgroundColor: "#4CAF50",
            color: "white",
            border: "none",
            borderRadius: "5px",
            cursor: "pointer",
          }}
        >
          Generate Clone
        </button>
      </div>

      {combinedHtml && (
        <>
          <h2 style={{ fontSize: "1.5rem", marginTop: "2rem" }}>
            Preview of Cloned Website
          </h2>
          <iframe
            srcDoc={combinedHtml}
            style={{
              width: "100%",
              height: "600px",
              border: "1px solid #333",
              marginTop: "1rem",
              backgroundColor: "white",
            }}
            title="Cloned Preview"
          ></iframe>

          <div style={{ marginTop: "2rem" }}>
            <h3 style={{ fontSize: "1.25rem", marginBottom: "0.5rem" }}>
              Combined HTML
            </h3>
            <pre
              style={{
                backgroundColor: "#fff",
                color: "#000",
                padding: "1rem",
                borderRadius: "5px",
                overflowX: "auto",
              }}
            >
              <code>{html}</code>
            </pre>

            <h3 style={{ fontSize: "1.25rem", marginTop: "1.5rem" }}>
              Combined CSS
            </h3>
            <pre
              style={{
                backgroundColor: "#fff",
                color: "#000",
                padding: "1rem",
                borderRadius: "5px",
                overflowX: "auto",
              }}
            >
              <code>{css}</code>
            </pre>
          </div>
        </>
      )}
    </div>
  );
}
