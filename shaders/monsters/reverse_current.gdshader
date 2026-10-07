shader_type canvas_item;
uniform vec4 flow_region = vec4(0.0, 0.0, 1.0, 1.0);
uniform float vigor : hint_range(0.0, 1.0) = 0.0;
uniform float h : hint_range(0.0, 1.0) = 1.0;
varying vec4 vertex_color;
void vertex(){vertex_color=COLOR;}
void fragment(){
    vec4 paint=texture(TEXTURE,UV);
    vec2 p=(UV-flow_region.xy)/flow_region.zw;
    float in_tail=step(0.0,p.x)*step(p.x,1.0)*step(0.0,p.y)*step(p.y,1.0);
    float light=dot(paint.rgb,vec3(0.299,0.587,0.114));
    float water=in_tail*smoothstep(0.47,0.80,light);
    // Advancing phase moves the bands toward smaller source Y: up the waterfall.
    float ribbon=pow(0.5+0.5*sin(p.y*29.0+sin(p.x*8.0)*0.6+TIME*(2.1+vigor*1.9)),4.0);
    float ripple=sin(p.y*48.0+p.x*12.0+TIME*3.2)*0.5+0.5;
    paint.rgb=mix(paint.rgb,paint.rgb*vec3(1.08,1.16,1.15),water*ribbon*(0.55+vigor*0.22));
    paint.rgb+=water*ripple*0.015;
    mat3 rgb_to_yiq=mat3(vec3(0.2989,0.5959,0.2115),vec3(0.5870,-0.2774,-0.5229),vec3(0.1140,-0.3216,0.3114));
    float angle=(1.0-h)*6.283185;
    mat3 rotation=mat3(vec3(1.0,0.0,0.0),vec3(0.0,cos(angle),-sin(angle)),vec3(0.0,sin(angle),cos(angle)));
    paint.rgb=inverse(rgb_to_yiq)*((rgb_to_yiq*paint.rgb)*rotation);
    COLOR=paint*vertex_color;
}
