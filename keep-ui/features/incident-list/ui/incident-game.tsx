import React, { useState, useEffect, useRef, useCallback } from 'react';


interface Props {
    onGameClose: () => void;
    incidentTitles: string[];
}


const IncidentCatcher = ({ onGameClose, incidentTitles }: Props) => {
  // State for the game
  const [isActive, setIsActive] = useState(true);
  const [overlayOpacity, setOverlayOpacity] = useState(0);
  const [score, setScore] = useState(0);
  const [lives, setLives] = useState(3);
  const [gameOver, setGameOver] = useState(false);
  const [incidents, setIncidents] = useState<Array<{
    id: number;
    position: { x: number; y: number };
    title: string;
  }>>([]);
  const [particles, setParticles] = useState<Array<{
    id: number;
    x: number;
    y: number;
    angle: number;
    speed: number;
    color: string;
    life: number;
  }>>([]);
  
  // Refs for game elements
  const gameContainerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<HTMLDivElement>(null);
  const animationFrameRef = useRef<number | null>(null);
  const lastTimestampRef = useRef(0);
  const nextIncidentTimeRef = useRef(0);
  const playerPositionRef = useRef(0);
  const keysRef = useRef<{ [key: string]: boolean }>({});
  const currentSpeedRef = useRef(2);
  const incidentIntervalRef = useRef(2000);

  // cut first 30 symbols from each incident title and add "..." if it's longer
  const activeIncidentTitles = incidentTitles.map(title => {
    if (title.length > 30) {
      return title.substring(0, 30) + ' ...';
    }
    return title;
  });

  // Initialize the game
  const initGame = useCallback(() => {
    setScore(0);
    setLives(3);
    setIncidents([]);
    setGameOver(false);
    
    currentSpeedRef.current = 2;
    incidentIntervalRef.current = 2000;
    nextIncidentTimeRef.current = 0;
    
    if (gameContainerRef.current && playerRef.current) {
      playerPositionRef.current = (gameContainerRef.current.clientWidth - playerRef.current.offsetWidth) / 2;
    }
    
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    animationFrameRef.current = requestAnimationFrame(gameLoop);
  }, []);

  // Fade in overlay effect
  useEffect(() => {
    if (isActive) {
      let opacity = 0;
      const interval = setInterval(() => {
        opacity += 0.05;
        if (opacity >= 0.7) {
          clearInterval(interval);
          opacity = 0.7;
        }
        setOverlayOpacity(opacity);
      }, 50);
      
      return () => clearInterval(interval);
    }
  }, [isActive]);
  
  // Initialize the game automatically when component mounts
  useEffect(() => {
    const timer = setTimeout(() => {
      initGame();
    }, 700); // Start after overlay animation
    
    return () => clearTimeout(timer);
  }, [initGame]);

  // Handle keyboard events
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      keysRef.current[e.key] = true;
    };
    
    const handleKeyUp = (e: KeyboardEvent) => {
      keysRef.current[e.key] = false;
    };
    
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [gameOver, initGame, onGameClose, score]);

  // Main game loop
  const gameLoop = useCallback((timestamp:any) => {
    if (gameOver) return;
    
    const deltaTime = timestamp - lastTimestampRef.current;
    lastTimestampRef.current = timestamp;
    
    // Move player
    movePlayer();
    
    // Create new incidents
    if (timestamp >= nextIncidentTimeRef.current) {
      createIncident();
      nextIncidentTimeRef.current = timestamp + incidentIntervalRef.current;
      
      // Decrease interval over time (make game harder)
      incidentIntervalRef.current = Math.max(500, incidentIntervalRef.current - 50);
      
      // Increase falling speed over time
      currentSpeedRef.current += 0.1;
    }
    
    // Move and check incidents
    moveIncidents();
    
    // Continue game loop
    animationFrameRef.current = requestAnimationFrame(gameLoop);
  }, [gameOver]);

  // Create a new incident
  const createIncident = useCallback(() => {
    if (!gameContainerRef.current) return;
    
    const maxX = gameContainerRef.current.clientWidth - 120; // incident width
    const x = Math.floor(Math.random() * maxX);
    const title = activeIncidentTitles[Math.floor(Math.random() * activeIncidentTitles.length)];
    
    const newIncident = {
      id: Date.now(),
      position: { x, y: 0 },
      title
    };
    
    setIncidents(prev => [...prev, newIncident]); 
  }, [activeIncidentTitles]);

  // Move player based on key presses
  const movePlayer = useCallback(() => {
    if (!gameContainerRef.current || !playerRef.current) return;
    
    const containerWidth = gameContainerRef.current.clientWidth;
    const playerWidth = playerRef.current.offsetWidth;
    
    if (keysRef.current.ArrowLeft) {
      playerPositionRef.current = Math.max(0, playerPositionRef.current - 10);
    }
    
    if (keysRef.current.ArrowRight) {
      playerPositionRef.current = Math.min(
        containerWidth - playerWidth,
        playerPositionRef.current + 10
      );
    }
  }, []);

  // Move all incidents and check for catches or misses
  const moveIncidents = useCallback(() => {
    if (!playerRef.current || !gameContainerRef.current) return;
    
    const playerLeft = playerPositionRef.current;
    const playerRight = playerLeft + playerRef.current.offsetWidth;
    const playerTop = playerRef.current.offsetTop;
    const containerHeight = gameContainerRef.current.clientHeight;
    
    setIncidents(prev => {
      // Create a new array with updated positions
      const updated = prev.map(incident => ({
        ...incident,
        position: {
          ...incident.position,
          y: incident.position.y + currentSpeedRef.current
        }
      }));
      
      // Filter out caught or missed incidents
      return updated.filter(incident => {
        const incidentLeft = incident.position.x;
        const incidentRight = incidentLeft + 120; // incident width
        const incidentBottom = incident.position.y + 40; // incident height
        
        // Check if caught
        if (incidentBottom >= playerTop && 
            playerRef.current &&
            incidentBottom <= playerTop + playerRef.current.offsetHeight &&
            incidentRight >= playerLeft &&
            incidentLeft <= playerRight) {
          
          // Caught incident
          setScore(s => s + 10);
          
          // Create particle burst at catch position
          createParticleBurst(
            (incidentLeft + incidentRight) / 2, 
            playerTop,
            incident.title.includes("Error") ? "#ff5555" : 
            incident.title.includes("GPU") ? "#ffaa00" : 
            incident.title.includes("Memory") ? "#55ff55" : "#5599ff"
          );
          
          return false;
        }
        
        // Check if missed
        if (incident.position.y > containerHeight) {
          // Missed incident
          setLives(l => {
            const newLives = l - 1;
            if (newLives <= 0) {
              endGame();
            }
            return newLives;
          });
          return false;
        }
        
        // Keep this incident
        return true;
      });
    });
  }, []);

  // Create particle burst
  const createParticleBurst = useCallback((x: number, y: number, color = "#ffffff") => {
    const particleCount = 10;
    const newParticles: Array<{
      id: number;
      x: number;
      y: number;
      angle: number;
      speed: number;
      color: string;
      life: number;
    }> = [];
    
    for (let i = 0; i < particleCount; i++) {
      const angle = (Math.PI * 2 * i) / particleCount;
      const speed = 1 + Math.random() * 3;
      const life = 100 + Math.random() * 300; // 100-600ms
      
      newParticles.push({
        id: Date.now() + i,
        x,
        y,
        angle,
        speed,
        color,
        life
      });
    }
    
    setParticles(prev => [...prev, ...newParticles]);
    
    // Cleanup particles after maximum lifetime
    setTimeout(() => {
      setParticles(prev => prev.filter(p => p.id < Date.now()));
    }, 100);
  }, []);
  
  // End game
  const endGame = useCallback(() => {
    setGameOver(true);
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
  }, [score]);
  
  // Render the individual particles
  const renderParticles = () => {
    return particles.map(particle => {
      const style: React.CSSProperties = {
        position: 'absolute' as const,
        left: `${particle.x}px`,
        top: `${particle.y}px`,
        width: '8px',
        height: '8px',
        backgroundColor: particle.color,
        transform: 'translate(-50%, -50%)'
      };
      
      return (
        <div 
          key={particle.id}
          className="particle"
          style={style}
          data-angle={particle.angle}
          data-speed={particle.speed}
          data-life={particle.life}
        />
      );
    });
  };
  
  // Update particle positions (using DOM methods to avoid too many rerenders)
  useEffect(() => {
    if (particles.length === 0) return;
    
    let frameId: number;
    const startTime = Date.now();
    
    const updateParticles = () => {
      const now = Date.now();
      const particleElements = document.querySelectorAll('.particle');
      
      particleElements.forEach((elem) => {
        const angle = parseFloat(elem.getAttribute('data-angle') || '0');
        const speed = parseFloat(elem.getAttribute('data-speed') || '0');
        const life = parseFloat(elem.getAttribute('data-life') || '0');
        const elapsed = now - startTime;
        
        if (elapsed < life) {
          // Calculate new position
          const htmlElem = elem as HTMLElement;
          const currentLeft = parseFloat(htmlElem.style.left);
          const currentTop = parseFloat(htmlElem.style.top);
          
          htmlElem.style.left = `${currentLeft + Math.cos(angle) * speed}px`;
          htmlElem.style.top = `${currentTop + Math.sin(angle) * speed}px`;
          
          // Set opacity based on remaining life
          const remainingLife = 1 - elapsed / life;
          htmlElem.style.opacity = remainingLife.toString();
        } else {
          // Particle expired
          (elem as HTMLElement).style.display = 'none';
        }
      });
      
      frameId = requestAnimationFrame(updateParticles);
    };
    
    frameId = requestAnimationFrame(updateParticles);
    
    return () => cancelAnimationFrame(frameId);
  }, [particles]);

  return (
    <div className="w-0 h-0">
      {/* Game overlay */}
      <div 
        className="fixed inset-0 flex items-center justify-center z-50"
        style={{ backgroundColor: `rgba(0, 0, 0, ${overlayOpacity})` }}
      >
        {/* Game panel */}
        <div className="bg-gray-800 border-4 border-gray-600 rounded-lg shadow-2xl w-full max-w-2xl relative">
          {/* Close button */}
          <button 
            onClick={() => {
              if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
              }
              setIsActive(false);
              setOverlayOpacity(0);
              onGameClose();
            }}
            className="absolute -top-6 -right-4 text-gray-300 hover:text-white z-10"
          >
            ✕
          </button>
          
          {/* Game container */}
          <div 
            ref={gameContainerRef}
            className="relative w-full h-96 bg-black overflow-hidden"
          >
            {/* Player */}
            <div 
              ref={playerRef}
              className="absolute w-24 h-5 bg-blue-500 border-2 border-white shadow-lg"
              style={{ 
                bottom: '20px', 
                left: `${playerPositionRef.current}px`,
                boxShadow: '0 0 5px #00f' 
              }}
            ></div>
            
            {/* Score display */}
            <div className="absolute top-2 left-2 text-white text-lg font-bold">
              SCORE: {score}
            </div>
            
            {/* Lives display */}
            <div className="absolute top-2 right-2 text-white text-lg font-bold">
              LIVES: {lives}
            </div>
            
            {/* Incidents */}
            {incidents.map(incident => (
              <div
                key={incident.id}
                className="absolute w-30 p-2 bg-red-500 text-white text-xs text-center rounded-lg border-2 border-white"
                style={{ 
                  left: `${incident.position.x}px`,
                  top: `${incident.position.y}px`,
                  width: '120px',
                  boxShadow: '0 0 5px #f00'
                }}
              >
                {incident.title}
              </div>
            ))}
            
            {/* Render particles (using simpler approach) */}
            {renderParticles()}
            
            {/* Game over message */}
            {gameOver && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black bg-opacity-70">
                <div className="text-red-500 text-4xl font-bold animate-pulse">
                  GAME OVER
                </div>
                <div className="text-white text-xl mt-4">
                  Final Score: {score}
                </div>
                <div className="text-gray-400 text-sm mt-2">
                  Work harder on your incidents next time.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default IncidentCatcher;