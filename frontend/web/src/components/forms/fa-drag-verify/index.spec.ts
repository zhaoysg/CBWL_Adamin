import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import FaDragVerify from "./index.vue";

Object.assign(globalThis, { computed, nextTick, onBeforeUnmount, onMounted, ref, watch });

describe("FaDragVerify", () => {
  it("continues dragging after the pointer leaves the slider track", async () => {
    const wrapper = mount(FaDragVerify, {
      global: {
        stubs: {
          FaSvgIcon: true,
        },
      },
    });

    await wrapper.find(".dv_handler").trigger("mousedown", { clientX: 0 });
    document.dispatchEvent(new MouseEvent("mousemove", { clientX: 220 }));
    await wrapper.vm.$nextTick();

    expect(wrapper.emitted("passCallback")).toHaveLength(1);
  });
});
