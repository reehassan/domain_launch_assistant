// src/components/Mascot.jsx
// Uses the real reference artwork (3 pose PNGs, cropped to an identical
// canvas size so swapping poses via state never shifts layout).

import idleImg from "../assets/mascot/mascot-idle.png";
import coveringImg from "../assets/mascot/mascot-covering.png";
import celebratingImg from "../assets/mascot/mascot-celebrating.png";

const POSES = {
  idle: idleImg,
  covering: coveringImg,
  celebrating: celebratingImg,
};

export default function Mascot({ pose = "idle", size = 64, className = "" }) {
  const src = POSES[pose] ?? idleImg;
  return (
    <img
      src={src}
      alt=""
      width={size}
      style={{ height: "auto" }}
      className={"select-none object-contain transition-transform duration-200 " + className}
      draggable={false}
    />
  );
}