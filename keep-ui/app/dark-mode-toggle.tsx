import { Icon, Switch } from "@tremor/react";
import { useEffect } from "react";
import { MdDarkMode } from "react-icons/md";
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
    <button
      className="flex items-center justify-between space-x-3 w-full text-sm p-1 text-gray-700 hover:bg-gray-200 font-medium rounded-lg hover:text-orange-500 focus:ring focus:ring-orange-300"
      onClick={toggleDarkMode}
    >
      <span className="flex items-center justify-between">
        <Icon className="text-gray-700" icon={MdDarkMode} color="orange" />
        <span>Dark Mode</span>
      </span>
      <Switch color="orange" checked={darkMode} />
    </button>
  );
}
