import { heroui } from "@heroui/react";

export default heroui({
  layout: {
    boxShadow: "none",
    borderWidth: "1px",
    radius: "0.375rem",
  },
  themes: {
    light: {
      colors: {
        background: "#FFFFFF",
        foreground: "#11181C",
        default: {
          50: "#FAFAFA",
          100: "#F4F4F5",
          200: "#E4E4E7",
          300: "#D4D4D8",
          400: "#A1A1AA",
          500: "#71717A",
          600: "#52525B",
          700: "#3F3F46",
          800: "#27272A",
          900: "#18181B",
          DEFAULT: "#71717A",
          foreground: "#FFFFFF",
        },
        primary: {
          50: "#E6F1FE",
          100: "#CCE3FD",
          200: "#99C7FB",
          300: "#66AAF9",
          400: "#338EF7",
          500: "#006FEE",
          600: "#005BC4",
          700: "#004493",
          800: "#002E62",
          900: "#001731",
          DEFAULT: "#006FEE",
          foreground: "#FFFFFF",
        },
      },
    },
  },
});
