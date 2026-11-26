import flagsmith from "flagsmith";

export function checkout(cart) {
  if (flagsmith.hasFeature("new_checkout")) {
    return newCheckout(cart);
  }
  return oldCheckout(cart);
}

export const banner = flagsmith.hasFeature('old_banner') ? "sale" : "";