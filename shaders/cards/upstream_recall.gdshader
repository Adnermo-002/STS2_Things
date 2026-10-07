shader_type canvas_item;
render_mode blend_mix;
varying vec4 vertex_color;
void vertex(){vertex_color=COLOR;}
void fragment(){
    vec2 p=UV;
    float distance_to_edge=min(min(p.x,1.0-p.x),min(p.y,1.0-p.y));
    float edge=(1.0-smoothstep(0.025,0.105,distance_to_edge));
    float waves=sin(p.y*28.0+TIME*2.1+sin(p.x*15.0)*0.7)*0.5+0.5;
    float stream=pow(waves,3.0);
    float inner=(1.0-smoothstep(0.01,0.055,abs(distance_to_edge-0.055)))*stream;
    vec3 color=mix(vec3(0.27,0.61,0.63),vec3(0.86,0.93,0.79),stream);
    float alpha=(edge*0.14+inner*0.36)*texture(TEXTURE,UV).a;
    COLOR=vec4(color,alpha)*vertex_color;
}
