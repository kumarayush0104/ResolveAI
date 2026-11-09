import { useEffect, useRef } from 'react'
import { useMotionValueEvent, type MotionValue } from 'framer-motion'
import * as THREE from 'three'

function createPayPalP() {
  const shape = new THREE.Shape()
  shape.moveTo(0, 0)
  shape.lineTo(0.48, 2.4)
  shape.lineTo(1.38, 2.4)
  shape.bezierCurveTo(1.8, 2.4, 2.04, 2.12, 1.98, 1.73)
  shape.bezierCurveTo(1.92, 1.33, 1.63, 1.08, 1.2, 1.08)
  shape.lineTo(0.82, 1.08)
  shape.lineTo(0.62, 0)
  shape.closePath()

  const counter = new THREE.Path()
  counter.moveTo(0.98, 1.55)
  counter.lineTo(1.31, 1.55)
  counter.bezierCurveTo(1.49, 1.55, 1.58, 1.7, 1.55, 1.84)
  counter.bezierCurveTo(1.52, 1.98, 1.42, 2.06, 1.27, 2.06)
  counter.lineTo(1.08, 2.06)
  counter.closePath()
  shape.holes.push(counter)

  return shape
}

function createWordmarkTexture() {
  const canvas = document.createElement('canvas')
  canvas.width = 900
  canvas.height = 240
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Unable to create the PayPal logo canvas texture.')

  context.font = 'italic 900 184px Arial, sans-serif'
  context.fillStyle = '#003087'
  context.textBaseline = 'middle'
  context.fillText('PayPal', 12, 126)

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 4
  return texture
}

export function ThreePayPalLogo({
  scrollProgress,
}: {
  scrollProgress: MotionValue<number>
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const groupRef = useRef<THREE.Group | null>(null)
  const materialRef = useRef<THREE.MeshStandardMaterial[]>([])
  const renderRef = useRef<(() => void) | null>(null)
  const pointerRef = useRef({ x: 0, y: 0 })
  const scrollRotationRef = useRef({ x: 0, y: 0 })

  useMotionValueEvent(scrollProgress, 'change', (progress) => {
    const group = groupRef.current
    if (!group) return

    const zoom = THREE.MathUtils.smoothstep(progress, 0.08, 0.34)
    const fade = 1 - THREE.MathUtils.smoothstep(progress, 0.33, 0.4)
    group.scale.setScalar(1 + zoom * 5.5)
    group.position.z = zoom * 1.4
    scrollRotationRef.current.y = progress * Math.PI * 0.48
    scrollRotationRef.current.x = progress * Math.PI * 0.12
    group.rotation.y = scrollRotationRef.current.y + pointerRef.current.x * 0.12
    group.rotation.x = scrollRotationRef.current.x + pointerRef.current.y * 0.08

    for (const material of materialRef.current) {
      material.opacity = fade
    }
    renderRef.current?.()
  })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const onPointerMove = (event: PointerEvent) => {
      const bounds = canvas.getBoundingClientRect()
      if (event.clientY < bounds.top || event.clientY > bounds.bottom) return
      pointerRef.current.x = THREE.MathUtils.clamp((event.clientX / window.innerWidth - 0.5) * 2, -1, 1)
      pointerRef.current.y = THREE.MathUtils.clamp((event.clientY / window.innerHeight - 0.5) * 2, -1, 1)

      const group = groupRef.current
      if (!group) return
      group.position.x = pointerRef.current.x * 0.2
      group.position.y = -pointerRef.current.y * 0.14
      group.rotation.y = scrollRotationRef.current.y + pointerRef.current.x * 0.12
      group.rotation.x = scrollRotationRef.current.x + pointerRef.current.y * 0.08
      renderRef.current?.()
    }

    const onPointerLeave = () => {
      pointerRef.current = { x: 0, y: 0 }
      const group = groupRef.current
      if (!group) return
      group.position.x = 0
      group.position.y = 0
      group.rotation.x = scrollRotationRef.current.x
      group.rotation.y = scrollRotationRef.current.y
      renderRef.current?.()
    }

    window.addEventListener('pointermove', onPointerMove, { passive: true })
    window.addEventListener('blur', onPointerLeave)
    return () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('blur', onPointerLeave)
    }
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true })
    } catch (error) {
      console.error('Unable to initialize the Three.js PayPal logo scene.', error)
      return
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setSize(canvas.clientWidth, canvas.clientHeight, false)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.1

    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-4.6, 4.6, 4.6, -4.6, 0.1, 100)
    camera.position.set(0, 0, 24)

    scene.add(new THREE.AmbientLight(0xffffff, 1.5))
    const keyLight = new THREE.DirectionalLight(0xffffff, 4)
    keyLight.position.set(-3, 5, 7)
    scene.add(keyLight)
    const rimLight = new THREE.PointLight(0x54c8ff, 16, 20)
    rimLight.position.set(3, -1, 4)
    scene.add(rimLight)

    const logoGroup = new THREE.Group()
    groupRef.current = logoGroup
    scene.add(logoGroup)

    const logoArtwork = new THREE.Group()
    logoArtwork.position.set(-3.2, -1.2, 0)
    logoGroup.add(logoArtwork)

    const paypalP = createPayPalP()
    const shapeGeometry = new THREE.ExtrudeGeometry(paypalP, {
      depth: 0.2,
      bevelEnabled: true,
      bevelSegments: 4,
      steps: 1,
      bevelSize: 0.035,
      bevelThickness: 0.045,
      curveSegments: 18,
    })
    shapeGeometry.computeVertexNormals()

    const navy = new THREE.MeshStandardMaterial({
      color: '#003087',
      metalness: 0.45,
      roughness: 0.24,
      transparent: true,
    })
    const cyan = new THREE.MeshStandardMaterial({
      color: '#009cde',
      metalness: 0.4,
      roughness: 0.22,
      transparent: true,
    })
    materialRef.current = [navy, cyan]

    const rearP = new THREE.Mesh(shapeGeometry, navy)
    rearP.position.set(0.13, 0.12, -0.02)
    logoArtwork.add(rearP)

    const frontP = new THREE.Mesh(shapeGeometry, cyan)
    frontP.position.set(-0.08, -0.1, 0.12)
    logoArtwork.add(frontP)

    const wordmarkTexture = createWordmarkTexture()
    const wordmarkMaterial = new THREE.MeshStandardMaterial({
      map: wordmarkTexture,
      transparent: true,
      roughness: 0.32,
      metalness: 0.18,
    })
    materialRef.current.push(wordmarkMaterial)
    const wordmark = new THREE.Mesh(new THREE.PlaneGeometry(4.35, 1.16), wordmarkMaterial)
    wordmark.position.set(4.28, 0.62, 0.1)
    logoArtwork.add(wordmark)

    const resize = () => {
      const width = canvas.clientWidth
      const height = canvas.clientHeight
      if (width === 0 || height === 0) return
      const aspect = width / height
      const viewWidth = 9.2
      const viewHeight = viewWidth / aspect
      camera.left = -viewWidth / 2
      camera.right = viewWidth / 2
      camera.top = viewHeight / 2
      camera.bottom = -viewHeight / 2
      camera.updateProjectionMatrix()
      renderer.setSize(width, height, false)
      renderer.render(scene, camera)
    }
    resize()
    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(canvas)

    renderRef.current = () => renderer.render(scene, camera)
    renderer.render(scene, camera)

    return () => {
      resizeObserver.disconnect()
      shapeGeometry.dispose()
      wordmark.geometry.dispose()
      wordmarkTexture.dispose()
      navy.dispose()
      cyan.dispose()
      wordmarkMaterial.dispose()
      renderer.dispose()
      renderRef.current = null
      groupRef.current = null
      materialRef.current = []
    }
  }, [])

  return <canvas ref={canvasRef} className="story-three-canvas" role="img" aria-label="Three-dimensional PayPal logo" />
}
