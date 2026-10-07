vec2 tiling_and_offset(vec2 base_uv, vec4 st, vec2 initial_offset) {
	return (
		(base_uv * st.xy) + 
		((st.zw * TIME) + initial_offset)
		);
}