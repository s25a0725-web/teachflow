/* TeachFlow — premium multicolour 3D neural network background.
 * Offline Three.js (r128). Renders an animated network of glowing nodes,
 * light pulses travelling along connections, translucent glass spheres and a
 * drifting particle field, with mouse parallax. Falls back silently to the
 * static CSS background when WebGL is unavailable or the user prefers
 * reduced motion.
 */
(function () {
  "use strict";
  if (typeof THREE === "undefined") return;

  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var touch = "ontouchstart" in window || navigator.maxTouchPoints > 0;
  var small = window.innerWidth < 768;

  var host = document.getElementById("neural");
  if (!host) return;

  // ---- Page-driven intensity -------------------------------------------------
  var page = (document.body && document.body.getAttribute("data-page")) || "dashboard";
  var CFG = {
    login:      { nodes: touch ? 55 : 90, links: 0.16, glass: 6, particles: 420, speed: 1.25, bloom: 1.0 },
    ai:         { nodes: touch ? 65 : 110, links: 0.18, glass: 8, particles: 520, speed: 1.35, bloom: 1.0 },
    docs:       { nodes: touch ? 50 : 80, links: 0.15, glass: 10, particles: 380, speed: 1.0, bloom: 0.9 },
    analytics:  { nodes: touch ? 55 : 85, links: 0.17, glass: 6, particles: 460, speed: 1.1, bloom: 0.95 },
    settings:   { nodes: touch ? 30 : 48, links: 0.12, glass: 4, particles: 240, speed: 0.8, bloom: 0.75 },
    dashboard:  { nodes: touch ? 42 : 70, links: 0.14, glass: 5, particles: 320, speed: 0.9, bloom: 0.85 },
  };
  var cfg = CFG[page] || CFG.dashboard;

  // ---- Colour palette (exclusive TeachFlow 2.0 neural identity) ---------------
  // Purple + blue dominate the structures; orange + red accent selected nodes,
  // pathways and energy particles. No green/yellow/pink/cyan.
  var COLORS = {
    purple: new THREE.Color("#873BFF"),
    blue:   new THREE.Color("#167BFF"),
    orange: new THREE.Color("#FF8A24"),
    red:    new THREE.Color("#F04452"),
  };
  var PALETTE = [
    COLORS.purple, COLORS.purple, COLORS.purple, COLORS.purple,
    COLORS.blue,   COLORS.blue,   COLORS.blue,   COLORS.blue,
    COLORS.orange, COLORS.red,
  ];
  function pick() { return PALETTE[(Math.random() * PALETTE.length) | 0]; }

  // ---- Renderer --------------------------------------------------------------
  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: !small, powerPreference: "low-power" });
  } catch (e) {
    return; // WebGL unavailable -> keep CSS fallback
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, small ? 1.5 : 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);
  host.appendChild(renderer.domElement);

  var scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0a0c18, 0.0009);

  var camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 2000);
  camera.position.z = 260;

  var BOUNDS = { x: 620, y: 380, z: 300 };

  // ---- Nodes (glowing spheres) ----------------------------------------------
  var nodeGroup = new THREE.Group();
  var nodes = [];
  for (var i = 0; i < cfg.nodes; i++) {
    var geo = new THREE.SphereGeometry(2.2 + Math.random() * 3.5, 12, 12);
    var mat = new THREE.MeshBasicMaterial({ color: pick(), transparent: true, opacity: 0.85 });
    var m = new THREE.Mesh(geo, mat);
    m.position.set(
      (Math.random() - 0.5) * BOUNDS.x,
      (Math.random() - 0.5) * BOUNDS.y,
      (Math.random() - 0.5) * BOUNDS.z
    );
    m.userData = {
      base: m.position.clone(),
      amp: 6 + Math.random() * 14,
      ph: Math.random() * Math.PI * 2,
      sp: 0.3 + Math.random() * 0.7,
      pulse: Math.random() < 0.35,
    };
    nodeGroup.add(m);
    nodes.push(m);
  }
  scene.add(nodeGroup);

  // ---- Connections (lines with travelling light pulses) ----------------------
  var lineGroup = new THREE.Group();
  var lines = [];
  var pulses = [];
  var linkDist = 175;
  for (var a = 0; a < nodes.length; a++) {
    for (var b = a + 1; b < nodes.length; b++) {
      if (Math.random() > cfg.links) continue;
      var d = nodes[a].position.distanceTo(nodes[b].position);
      if (d > linkDist) continue;
      var geo2 = new THREE.BufferGeometry().setFromPoints([nodes[a].position, nodes[b].position]);
      var mat2 = new THREE.LineBasicMaterial({ color: 0x167bff, transparent: true, opacity: 0.16 });
      var ln = new THREE.Line(geo2, mat2);
      lineGroup.add(ln);
      lines.push({ line: ln, a: a, b: b });
    }
  }
  // travelling pulses: small bright spheres moving along a subset of links
  for (var p = 0; p < Math.min(40, lines.length); p++) {
    if (Math.random() > 0.5) continue;
    var pl = lines[(Math.random() * lines.length) | 0];
    var pgeo = new THREE.SphereGeometry(1.6, 8, 8);
    var pmat = new THREE.MeshBasicMaterial({ color: pick(), transparent: true, opacity: 0.95 });
    var pulse = new THREE.Mesh(pgeo, pmat);
    pulse.userData = { link: pl, t: Math.random(), sp: 0.4 + Math.random() * 0.9 };
    lineGroup.add(pulse);
    pulses.push(pulse);
  }
  scene.add(lineGroup);

  // ---- Glass spheres (translucent, slow float) ------------------------------
  var glassGroup = new THREE.Group();
  var glass = [];
  for (var g = 0; g < cfg.glass; g++) {
    var ggeo = new THREE.SphereGeometry(9 + Math.random() * 22, 20, 20);
    var gmat = new THREE.MeshPhongMaterial({
      color: pick(), transparent: true, opacity: 0.08,
      shininess: 60, specular: new THREE.Color("#ffffff"),
    });
    var gm = new THREE.Mesh(ggeo, gmat);
    gm.position.set((Math.random() - 0.5) * BOUNDS.x * 1.3, (Math.random() - 0.5) * BOUNDS.y * 1.1, -40 - Math.random() * 260);
    gm.userData = { base: gm.position.clone(), amp: 8 + Math.random() * 16, ph: Math.random() * 6.28, sp: 0.15 + Math.random() * 0.3 };
    glassGroup.add(gm);
    glass.push(gm);
  }
  scene.add(glassGroup);

  // ---- Particle field --------------------------------------------------------
  var pCount = cfg.particles;
  var pPos = new Float32Array(pCount * 3);
  for (var q = 0; q < pCount; q++) {
    pPos[q * 3] = (Math.random() - 0.5) * BOUNDS.x * 1.6;
    pPos[q * 3 + 1] = (Math.random() - 0.5) * BOUNDS.y * 1.4;
    pPos[q * 3 + 2] = (Math.random() - 0.5) * BOUNDS.z * 1.2;
  }
  var pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3));
  var pMat = new THREE.PointsMaterial({ color: 0x167bff, size: 1.3, transparent: true, opacity: 0.5, sizeAttenuation: true });
  var points = new THREE.Points(pGeo, pMat);
  scene.add(points);

  // ---- Lighting --------------------------------------------------------------
  var amb = new THREE.AmbientLight(0x1a1a2e, 1.4);
  var dir = new THREE.DirectionalLight(0xffffff, 0.6);
  dir.position.set(1, 1, 1);
  scene.add(amb, dir);
  var purpleL = new THREE.PointLight(0x873bff, 1.0, 900); purpleL.position.set(300, 150, 200); scene.add(purpleL);
  var blueL = new THREE.PointLight(0x167bff, 0.9, 900); blueL.position.set(-320, -140, 180); scene.add(blueL);
  var orangeL = new THREE.PointLight(0xff8a24, 0.6, 900); orangeL.position.set(0, 260, -80); scene.add(orangeL);
  var redL = new THREE.PointLight(0xf04452, 0.5, 900); redL.position.set(180, -220, -120); scene.add(redL);

  // ---- Mouse parallax --------------------------------------------------------
  var mouse = { x: 0, y: 0, tx: 0, ty: 0 };
  if (!touch) {
    window.addEventListener("mousemove", function (e) {
      mouse.tx = (e.clientX / window.innerWidth - 0.5) * 2;
      mouse.ty = (e.clientY / window.innerHeight - 0.5) * 2;
    }, { passive: true });
  }

  // ---- Resize -----------------------------------------------------------------
  window.addEventListener("resize", function () {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }, { passive: true });

  // ---- Animation loop ---------------------------------------------------------
  var clock = new THREE.Clock();
  var active = page === "ai" || page === "login";
  var targetRotation = { x: 0, y: 0 };

  function animate() {
    if (reduced) { renderer.render(scene, camera); return; } // single static frame
    var t = clock.getElapsedTime() * cfg.speed;

    // floating nodes
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i], u = n.userData;
      n.position.y = u.base.y + Math.sin(t * u.sp + u.ph) * u.amp * 0.5;
      n.position.x = u.base.x + Math.cos(t * u.sp * 0.8 + u.ph) * u.amp * 0.35;
      if (u.pulse) {
        var s = 1 + Math.sin(t * 2 + u.ph) * 0.18;
        n.scale.setScalar(s);
      }
    }

    // travelling pulses
    for (var j = 0; j < pulses.length; j++) {
      var pu = pulses[j], L = pu.userData.link;
      pu.userData.t += 0.0025 * pu.userData.sp * (active ? 1.6 : 1);
      if (pu.userData.t > 1) { pu.userData.t = 0; }
      var A = nodes[L.a].position, B = nodes[L.b].position;
      pu.position.lerpVectors(A, B, pu.userData.t);
      pu.material.opacity = Math.sin(pu.userData.t * Math.PI) * 0.9;
    }

    // glass float
    for (var k = 0; k < glass.length; k++) {
      var gl = glass[k], gu = gl.userData;
      gl.position.y = gu.base.y + Math.sin(t * gu.sp + gu.ph) * gu.amp;
      gl.rotation.y += 0.0015;
      gl.rotation.x += 0.0008;
    }

    // particle drift
    var pos = pGeo.attributes.position.array;
    for (var m = 0; m < pCount; m++) {
      pos[m * 3 + 1] += 0.06;
      if (pos[m * 3 + 1] > BOUNDS.y * 0.7) pos[m * 3 + 1] = -BOUNDS.y * 0.7;
    }
    pGeo.attributes.position.needsUpdate = true;

    // mouse parallax + gentle idle rotation
    mouse.x += (mouse.tx - mouse.x) * 0.04;
    mouse.y += (mouse.ty - mouse.y) * 0.04;
    targetRotation.y += 0.0012;
    nodeGroup.rotation.y = targetRotation.y + mouse.x * 0.12;
    nodeGroup.rotation.x = mouse.y * -0.08;
    lineGroup.rotation.copy(nodeGroup.rotation);
    glassGroup.rotation.y = -targetRotation.y * 0.5 + mouse.x * 0.06;
    camera.position.x = mouse.x * 26;
    camera.position.y = -mouse.y * 18;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }
  animate();

  // pause when hidden (save GPU/CPU)
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { clock.stop(); } else { clock.start(); }
  });
})();
