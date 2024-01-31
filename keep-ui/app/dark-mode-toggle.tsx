import { Switch, Text } from "@tremor/react";
import { useEffect } from "react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

export default function DarkModeToggle() {
  const [darkMode, setDarkMode] = useLocalStorage("darkMode", false);

  const applyDarkModeStyles = () => {
    /**
     * Taken from https://dev.to/jochemstoel/re-add-dark-mode-to-any-website-with-just-a-few-lines-of-code-phl
     */
    var h = document.getElementsByTagName("head")[0],
      s = document.createElement("style");
    s.setAttribute("type", "text/css");
    s.setAttribute("id", "nightify");
    s.appendChild(
      document.createTextNode(
        "html{-webkit-filter:invert(100%) hue-rotate(180deg) contrast(70%) !important; background: #fff;} .line-content {background-color: #fefefe;}"
      )
    );
    h.appendChild(s);
  };

  const toggleDarkMode = () => {
    /**
     * Taken from https://dev.to/jochemstoel/re-add-dark-mode-to-any-website-with-just-a-few-lines-of-code-phl
     */
    setDarkMode(!darkMode);
    let q = document.querySelectorAll("#nightify");
    if (q.length) {
      q.forEach((q) => q.parentNode?.removeChild(q));
      return false;
    }
    applyDarkModeStyles();
  };

  useEffect(() => {
    if (darkMode) {
      applyDarkModeStyles();
    }
  }, [darkMode]);

  return (
    <div className="fixed right-2 mt-3">
      <div className="flex flex-col items-center">
        <Text>Dark Mode</Text>
        <Switch
          color="orange"
          onClick={toggleDarkMode}
          checked={darkMode}
        ></Switch>
      </div>
    </div>
  );
}
