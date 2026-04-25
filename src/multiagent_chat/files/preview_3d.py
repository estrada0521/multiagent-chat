from __future__ import annotations

from html import escape as html_escape


def _model_shell(
    *,
    filename: str,
    header_html: str,
    base_css: str,
    embed_bg: str,
    pane_muted: str,
    pane_line: str,
    meta_label: str,
    script: str,
) -> str:
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
        f"<style>{base_css}"
        f".wrap{{flex:1;min-height:0;display:flex;flex-direction:column;background:{embed_bg}}}"
        f".model{{flex:1;min-height:0;position:relative}}"
        f".model canvas{{width:100%;height:100%;display:block;touch-action:none;background:radial-gradient(circle at 50% 35%, rgba(255,255,255,0.04), rgba(255,255,255,0.01) 38%, rgba(0,0,0,0) 70%)}}"
        f".controls{{position:absolute;top:12px;right:12px;display:flex;gap:8px;z-index:2}}"
        f".controls button{{width:36px;height:36px;border:0.5px solid {pane_line};border-radius:10px;background:rgba(0,0,0,0.28);color:{pane_muted};font:inherit;font-size:18px;line-height:1;cursor:pointer;backdrop-filter:blur(8px)}}"
        f".meta{{padding:8px 16px 12px;color:{pane_muted};font-size:12px;border-top:0.5px solid {pane_line}}}"
        f"</style></head>"
        f'<body>{header_html}<div class="wrap"><div id="modelWrap" class="model"><div class="controls"><button type="button" id="zoomInBtn" aria-label="Zoom in">+</button><button type="button" id="zoomOutBtn" aria-label="Zoom out">-</button><button type="button" id="zoomResetBtn" aria-label="Reset zoom">·</button></div><canvas id="modelCanvas"></canvas></div><div id="modelMeta" class="meta">{meta_label}</div></div><script>{script}</script></body></html>'
    )


def _base_canvas_js() -> str:
    return (
        'const wrap=document.getElementById("modelWrap");'
        'const meta=document.getElementById("modelMeta");'
        'const canvas=document.getElementById("modelCanvas");'
        'const zoomInBtn=document.getElementById("zoomInBtn");'
        'const zoomOutBtn=document.getElementById("zoomOutBtn");'
        'const zoomResetBtn=document.getElementById("zoomResetBtn");'
        'const ctx=canvas.getContext("2d");'
        'let verts=[],edges=[],angleX=-0.45,angleY=0.72,drag=false,lastX=0,lastY=0,scale=1,zoom=1,pinchStartDist=0,pinchStartZoom=1;'
        'const activePointers=new Map();'
        'const clampZoom=(value)=>Math.min(8,Math.max(0.35,value));'
        'const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);'
        'const setZoom=(value)=>{zoom=clampZoom(value);draw();};'
        'const fit=()=>{const dpr=Math.max(1,window.devicePixelRatio||1);const w=Math.max(1,wrap.clientWidth);const h=Math.max(1,wrap.clientHeight);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);canvas.style.width=w+"px";canvas.style.height=h+"px";ctx.setTransform(dpr,0,0,dpr,0,0);draw();};'
        'const centerAndScale=(label)=>{if(!verts.length)return;let minX=Infinity,minY=Infinity,minZ=Infinity,maxX=-Infinity,maxY=-Infinity,maxZ=-Infinity;'
        'verts.forEach(([x,y,z])=>{if(x<minX)minX=x;if(y<minY)minY=y;if(z<minZ)minZ=z;if(x>maxX)maxX=x;if(y>maxY)maxY=y;if(z>maxZ)maxZ=z;});'
        'const cx=(minX+maxX)/2,cy=(minY+maxY)/2,cz=(minZ+maxZ)/2;const sx=maxX-minX,sy=maxY-minY,sz=maxZ-minZ;const span=Math.max(sx,sy,sz,1e-6);scale=1.7/span;'
        'zoom=1;'
        'verts=verts.map(([x,y,z])=>[(x-cx)*scale,(y-cy)*scale,(z-cz)*scale]);meta.textContent=`${label} · ${verts.length} vertices · ${edges.length} edges · ${sx.toFixed(3)} x ${sy.toFixed(3)} x ${sz.toFixed(3)}`;};'
        'const project=([x,y,z],w,h)=>{const cosY=Math.cos(angleY),sinY=Math.sin(angleY),cosX=Math.cos(angleX),sinX=Math.sin(angleX);'
        'const x1=x*cosY-z*sinY;const z1=x*sinY+z*cosY;const y2=y*cosX-z1*sinX;const z2=y*sinX+z1*cosX+4.5;const f=Math.min(w,h)*0.34*zoom;return [w/2+x1*f/z2,h/2-y2*f/z2,z2];};'
        'const draw=()=>{const w=Math.max(1,wrap.clientWidth),h=Math.max(1,wrap.clientHeight);ctx.clearRect(0,0,w,h);ctx.fillStyle="rgba(255,255,255,0.02)";ctx.fillRect(0,0,w,h);'
        'ctx.strokeStyle="rgba(232,235,255,0.92)";ctx.lineWidth=1.15;ctx.beginPath();'
        'edges.forEach(([a,b])=>{const pa=project(verts[a],w,h),pb=project(verts[b],w,h);ctx.moveTo(pa[0],pa[1]);ctx.lineTo(pb[0],pb[1]);});ctx.stroke();};'
        'canvas.addEventListener("wheel",(e)=>{e.preventDefault();const factor=e.deltaY<0?1.12:1/1.12;setZoom(zoom*factor);},{passive:false});'
        'canvas.addEventListener("pointerdown",(e)=>{activePointers.set(e.pointerId,{x:e.clientX,y:e.clientY});canvas.setPointerCapture(e.pointerId);'
        'if(activePointers.size===1){drag=true;lastX=e.clientX;lastY=e.clientY;}'
        'else if(activePointers.size===2){const pts=[...activePointers.values()];pinchStartDist=Math.max(distance(pts[0],pts[1]),1);pinchStartZoom=zoom;drag=false;}});'
        'canvas.addEventListener("pointermove",(e)=>{if(!activePointers.has(e.pointerId))return;activePointers.set(e.pointerId,{x:e.clientX,y:e.clientY});'
        'if(activePointers.size===2){const pts=[...activePointers.values()];setZoom(pinchStartZoom*(distance(pts[0],pts[1])/Math.max(pinchStartDist,1)));return;}'
        'if(!drag)return;const dx=e.clientX-lastX,dy=e.clientY-lastY;lastX=e.clientX;lastY=e.clientY;angleY+=dx*0.01;angleX+=dy*0.01;draw();});'
        'const endDrag=(e)=>{activePointers.delete(e.pointerId);drag=activePointers.size===1;'
        'const remaining=[...activePointers.values()][0];if(remaining){lastX=remaining.x;lastY=remaining.y;}'
        'try{canvas.releasePointerCapture(e.pointerId);}catch(_){}'
        'if(activePointers.size===2){const pts=[...activePointers.values()];pinchStartDist=Math.max(distance(pts[0],pts[1]),1);pinchStartZoom=zoom;}};'
        'canvas.addEventListener("pointerup",endDrag);canvas.addEventListener("pointercancel",endDrag);'
        'zoomInBtn.addEventListener("click",()=>setZoom(zoom*1.2));'
        'zoomOutBtn.addEventListener("click",()=>setZoom(zoom/1.2));'
        'zoomResetBtn.addEventListener("click",()=>setZoom(1));'
        'window.addEventListener("resize",fit);fit();'
    )


def _obj_preview_script(raw_url: str) -> str:
    return (
        _base_canvas_js()
        + 'const parseObj=(text)=>{const v=[];const e=new Set();text.split(/\\r?\\n/).forEach((line)=>{const t=line.trim();if(!t||t[0]==="#")return;'
        'if(t.startsWith("v ")){const p=t.split(/\\s+/);if(p.length>=4)v.push([parseFloat(p[1])||0,parseFloat(p[2])||0,parseFloat(p[3])||0]);return;}'
        'if(t.startsWith("f ")){const p=t.split(/\\s+/).slice(1).map((item)=>parseInt((item.split("/")[0]||"0"),10)-1).filter((n)=>n>=0);'
        'for(let i=0;i<p.length;i+=1){const a=p[i],b=p[(i+1)%p.length];if(a===b)continue;const key=a<b?`${a}-${b}`:`${b}-${a}`;e.add(key);}return;}});'
        'return {verts:v,edges:[...e].map((key)=>key.split("-").map((n)=>parseInt(n,10)))};};'
        f'fetch("{raw_url}").then((res)=>res.text()).then((text)=>{{const parsed=parseObj(text);verts=parsed.verts;edges=parsed.edges;centerAndScale("OBJ preview");fit();}}).catch((err)=>{{meta.textContent="OBJ preview unavailable";console.error(err);}});'
    )


def _stl_preview_script(raw_url: str) -> str:
    return (
        _base_canvas_js()
        + 'const addTriangle=(a,b,c)=>{const base=verts.length;verts.push(a,b,c);edges.push([base,base+1],[base+1,base+2],[base+2,base]);};'
        'const parseAsciiStl=(text)=>{const matches=[...text.matchAll(/vertex\\s+([-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?)\\s+([-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?)\\s+([-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?)/g)];'
        'for(let i=0;i+2<matches.length;i+=3){const a=[parseFloat(matches[i][1]),parseFloat(matches[i][2]),parseFloat(matches[i][3])];const b=[parseFloat(matches[i+1][1]),parseFloat(matches[i+1][2]),parseFloat(matches[i+1][3])];const c=[parseFloat(matches[i+2][1]),parseFloat(matches[i+2][2]),parseFloat(matches[i+2][3])];addTriangle(a,b,c);}return matches.length>=3;};'
        'const parseBinaryStl=(buf)=>{const view=new DataView(buf);if(view.byteLength<84)return false;const triCount=view.getUint32(80,true);if(84+triCount*50!==view.byteLength)return false;let off=84;'
        'for(let i=0;i<triCount;i+=1){off+=12;const a=[view.getFloat32(off,true),view.getFloat32(off+4,true),view.getFloat32(off+8,true)];off+=12;const b=[view.getFloat32(off,true),view.getFloat32(off+4,true),view.getFloat32(off+8,true)];off+=12;const c=[view.getFloat32(off,true),view.getFloat32(off+4,true),view.getFloat32(off+8,true)];off+=12;addTriangle(a,b,c);off+=2;}return triCount>0;};'
        'const parseStl=(buf)=>{const isBinary=buf.byteLength>=84&&(84+new DataView(buf).getUint32(80,true)*50===buf.byteLength);if(isBinary)return parseBinaryStl(buf);const text=new TextDecoder().decode(buf);return parseAsciiStl(text);};'
        f'fetch("{raw_url}").then((res)=>res.arrayBuffer()).then((buf)=>{{if(!parseStl(buf))throw new Error("invalid stl");centerAndScale("STL preview");fit();}}).catch((err)=>{{meta.textContent="STL preview unavailable";console.error(err);}});'
    )


def render_3d_preview(
    *,
    ext: str,
    filename: str,
    header_html: str,
    raw_url: str,
    base_css: str,
    embed_bg: str,
    pane_muted: str,
    pane_line: str,
) -> str:
    if ext == ".obj":
        return _model_shell(
            filename=filename,
            header_html=header_html,
            base_css=base_css,
            embed_bg=embed_bg,
            pane_muted=pane_muted,
            pane_line=pane_line,
            meta_label="OBJ preview",
            script=_obj_preview_script(raw_url),
        )
    if ext == ".stl":
        return _model_shell(
            filename=filename,
            header_html=header_html,
            base_css=base_css,
            embed_bg=embed_bg,
            pane_muted=pane_muted,
            pane_line=pane_line,
            meta_label="STL preview",
            script=_stl_preview_script(raw_url),
        )
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html_escape(filename)}</title>'
        f'<style>{base_css}.wrap{{flex:1;display:flex;align-items:center;justify-content:center;padding:24px;background:{embed_bg};color:{pane_muted};text-align:center}}</style></head>'
        f'<body>{header_html}<div class="wrap">{html_escape(ext[1:].upper())} preview is not implemented yet.</div></body></html>'
    )
