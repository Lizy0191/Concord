import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import maplibregl from "maplibre-gl";
import { api } from "../api/client";

export default function GISWorkspace({
  project,
  selected,
  onSelected,
}: {
  project: string;
  selected: string;
  onSelected: (id: string) => void;
}) {
  const target = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const selection = useRef(onSelected);
  selection.current = onSelected;
  const data = useQuery({
    queryKey: ["geo", project],
    queryFn: () => api.geo(project),
  });
  useEffect(() => {
    if (!target.current || !data.data) return;
    let instance: maplibregl.Map | undefined;
    let observer: ResizeObserver | undefined;
    let disposed = false;
    setReady(false);
    setError("");
    const fail = (cause: unknown) => {
      if (!disposed) {
        setReady(false);
        setError(
          cause instanceof Error ? cause.message : "WebGL map unavailable",
        );
      }
    };
    const dispose = () => {
      disposed = true;
      observer?.disconnect();
      if (map.current === instance) map.current = null;
      instance?.remove();
    };
    try {
      const created = new maplibregl.Map({
        container: target.current,
        center: [120.36, 36.07],
        zoom: 17,
        attributionControl: false,
        style: {
          version: 8,
          sources: {},
          layers: [
            {
              id: "background",
              type: "background",
              paint: { "background-color": "#eef2ef" },
            },
          ],
        },
      });
      instance = created;
      map.current = created;
      created.addControl(new maplibregl.NavigationControl(), "top-right");
      created.on("load", () => {
        if (disposed) return;
        try {
          created.addSource("site", { type: "geojson", data: data.data! });
          created.addLayer({
            id: "areas",
            type: "fill",
            source: "site",
            filter: ["==", ["geometry-type"], "Polygon"],
            paint: { "fill-color": "#b3d0c4", "fill-opacity": 0.6 },
          });
          created.addLayer({
            id: "outline",
            type: "line",
            source: "site",
            filter: ["==", ["geometry-type"], "Polygon"],
            paint: { "line-color": "#5f8f7e", "line-width": 2 },
          });
          created.addLayer({
            id: "packages",
            type: "circle",
            source: "site",
            filter: ["==", ["geometry-type"], "Point"],
            paint: {
              "circle-radius": 8,
              "circle-color": "#236f61",
              "circle-stroke-color": "#fff",
              "circle-stroke-width": 3,
            },
          });
          created.on("click", "packages", (event) => {
            if (disposed) return;
            const feature = event.features?.[0];
            if (!feature) return;
            const workPackage = feature.properties?.work_package_id;
            if (typeof workPackage === "string") selection.current(workPackage);
            new maplibregl.Popup()
              .setLngLat(event.lngLat)
              .setText(
                String(
                  feature.properties?.name ?? workPackage ?? "Site location",
                ),
              )
              .addTo(created);
          });
          setReady(true);
        } catch (cause) {
          fail(cause);
        }
      });
      created.on("error", (event) => fail(event.error));
      observer = new ResizeObserver(() => {
        if (!disposed) created.resize();
      });
      observer.observe(target.current);
    } catch (cause) {
      fail(cause);
      // Construction may succeed before a control/observer fails. Do not leak
      // its canvas, WebGL context or worker when the effect has no normal return.
      dispose();
      return;
    }
    return dispose;
  }, [data.data]);
  useEffect(() => {
    const instance = map.current;
    if (!instance || !ready) return;
    if (instance.getLayer("packages"))
      instance.setPaintProperty("packages", "circle-radius", [
        "case",
        ["==", ["get", "work_package_id"], selected],
        12,
        8,
      ]);
  }, [selected, data.data, ready]);
  return (
    <section className="gis-workspace">
      <div className="viewer-toolbar">
        <strong>SITE CONTEXT</strong>
        <span>Local GeoJSON / no commercial tiles / synthetic location</span>
        <span role="status">
          {ready ? "Site map ready" : "Loading site map"}
        </span>
      </div>
      <div
        className="map-stage"
        ref={target}
        aria-label="Interactive project site map"
      />
      {(error || data.error) && (
        <div className="viewer-message" role="alert">
          Map unavailable: {error || data.error?.message}. Work packages remain
          available in the list view.
        </div>
      )}
    </section>
  );
}
