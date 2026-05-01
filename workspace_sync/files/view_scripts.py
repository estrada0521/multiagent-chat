from __future__ import annotations

import json


def build_vertical_bias_wheel_js(*, view_container_id: str, code_scroll_id: str) -> str:
        return (
            f'const viewContainer=document.getElementById("{view_container_id}");'
            f'const codeScroll=document.getElementById("{code_scroll_id}");'
            "const verticalBiasWheel=(event)=>{"
            "if(!viewContainer||!codeScroll)return;"
            "const verticalScrollTarget=(codeScroll.scrollHeight>codeScroll.clientHeight+1)?codeScroll:viewContainer;"
            "const absX=Math.abs(event.deltaX||0);"
            "const absY=Math.abs(event.deltaY||0);"
            "if(absX<0.5||absY<=absX*1.2)return;"
            "event.preventDefault();"
            "verticalScrollTarget.scrollTop += event.deltaY;"
            "};"
            'codeScroll?.addEventListener("wheel",verticalBiasWheel,{passive:false});'
        )

def build_gutter_scroll_sync_js(
        *,
        code_scroll_id: str,
        gutter_id: str,
        gutter_inner_id: str,
    ) -> str:
        return (
            f'const gutterSyncScroll=document.getElementById("{code_scroll_id}");'
            f'const gutterSyncSurface=document.getElementById("{gutter_id}");'
            f'const gutterSyncInner=document.getElementById("{gutter_inner_id}");'
            "const syncPreviewGutterScroll=()=>{"
            "if(!gutterSyncScroll||!gutterSyncInner)return;"
            "gutterSyncInner.style.transform=`translateY(${-gutterSyncScroll.scrollTop}px)`;"
            "};"
            "const forwardGutterWheel=(event)=>{"
            "if(!gutterSyncScroll)return;"
            "const absX=Math.abs(event.deltaX||0);"
            "const absY=Math.abs(event.deltaY||0);"
            "if(absX<0.5&&absY<0.5)return;"
            "event.preventDefault();"
            "gutterSyncScroll.scrollLeft += event.deltaX;"
            "gutterSyncScroll.scrollTop += event.deltaY;"
            "syncPreviewGutterScroll();"
            "};"
            'gutterSyncScroll?.addEventListener("scroll",syncPreviewGutterScroll,{passive:true});'
            'gutterSyncSurface?.addEventListener("wheel",forwardGutterWheel,{passive:false});'
            "syncPreviewGutterScroll();"
        )

def build_line_selection_js(
        *,
        table_selector: str,
        gutter_selector: str | None = None,
    ) -> str:
        gutter_query = (
            f"document.querySelector({json.dumps(gutter_selector)})"
            if gutter_selector
            else "null"
        )
        return (
            f'const selectableTable=document.querySelector({json.dumps(table_selector)});'
            f"const selectableGutter={gutter_query};"
            "if(selectableTable){"
            'let selectedLine="";'
            "const setSelectedLine=(lineValue)=>{"
            'const nextLine=String(lineValue||"");'
            "if(!nextLine||selectedLine===nextLine)return;"
            "if(selectedLine){"
            'selectableTable.querySelector(`tr[data-line="${selectedLine}"]`)?.classList.remove("is-selected");'
            'selectableGutter?.querySelector(`tr[data-line="${selectedLine}"]`)?.classList.remove("is-selected");'
            "}"
            "selectedLine=nextLine;"
            'selectableTable.querySelector(`tr[data-line="${selectedLine}"]`)?.classList.add("is-selected");'
            'selectableGutter?.querySelector(`tr[data-line="${selectedLine}"]`)?.classList.add("is-selected");'
            "};"
            "const bindSelectableSurface=(surface)=>{"
            "if(!surface)return;"
            'surface.addEventListener("click",(event)=>{'
            "const target=event.target;"
            "if(!(target instanceof Element))return;"
            'const row=target.closest("tr[data-line]");'
            "if(!row||!surface.contains(row))return;"
            'setSelectedLine(row.getAttribute("data-line"));'
            "});"
            "};"
            "bindSelectableSurface(selectableTable);"
            "bindSelectableSurface(selectableGutter);"
            "}"
        )

def build_progressive_loader_js(
        *,
        raw_url_value: str,
        text_ext: str,
        total_bytes: int,
        chunk_bytes: int,
        view_container_id: str,
        code_scroll_id: str,
        gutter_body_id: str,
        code_body_id: str,
    ) -> str:
        return (
            f"const rawUrl={json.dumps(raw_url_value)};"
            f"const fileExt={json.dumps(text_ext)};"
            f"const totalBytes={int(total_bytes)};"
            f"const chunkBytes={int(chunk_bytes)};"
            f'const progressiveViewContainer=document.getElementById("{view_container_id}");'
            f'const progressiveCodeScroll=document.getElementById("{code_scroll_id}");'
            f'const progressiveGutterBody=document.getElementById("{gutter_body_id}");'
            f'const progressiveCodeBody=document.getElementById("{code_body_id}");'
            "const progressiveScrollTarget=progressiveCodeScroll||progressiveViewContainer;"
            "if(progressiveViewContainer&&progressiveGutterBody&&progressiveCodeBody&&progressiveScrollTarget){"
            "const decoder=new TextDecoder();"
            "let offset=0;let loading=false;let done=false;let pending='';let lineNo=1;"
            "const setStatus=()=>{};"
            "const escapeHtml=(text)=>String(text||'').replace(/[&<>\"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[char]||char));"
            "const applyOutsideTags=(value,pattern,replacement)=>value.split(/(<[^>]*>)/g).map((part)=>part.startsWith('<')?part:part.replace(pattern,replacement)).join('');"
            "const highlightText=(text,ext)=>{"
            " let out=escapeHtml(text);"
            " if(['.py','.sh','.yaml','.yml'].includes(ext)){out=out.replace(/(^[ \\t]*#[^\\n]*)/gm,'<span style=\"color:#5c6370\">$1</span>');}"
            " else if(['.js','.ts','.css','.sql','.json'].includes(ext)){out=out.replace(/(\\/\\/[^\\n]*)/g,'<span style=\"color:#5c6370\">$1</span>');}"
            " else if(ext==='.tex'){out=out.replace(/(^[ \\t]*%[^\\n]*)/gm,'<span style=\"color:#5c6370\">$1</span>');}"
            " out=applyOutsideTags(out,/(\"(?:[^\"\\\\<\\n]|\\\\.)*\"|'(?:[^'\\\\<\\n]|\\\\.)*')/g,'<span style=\"color:#98c379\">$1</span>');"
            " out=applyOutsideTags(out,/(^|[^\\w#])(-?\\d+(?:\\.\\d+)?)/g,'$1<span style=\"color:#d19a66\">$2</span>');"
            " if(['.json','.yaml','.yml'].includes(ext)){out=applyOutsideTags(out,/(^[ \\t-]*)([A-Za-z_][\\w.-]*)(\\s*:)/gm,'$1<span style=\"color:#56b6c2\">$2</span>$3');}"
            " if(ext==='.tex'){out=applyOutsideTags(out,/(\\\\[A-Za-z@]+)/g,'<span style=\"color:#e06c75\">$1</span>');}"
            " if(ext==='.html'){out=applyOutsideTags(out,/(&lt;\\/?)([A-Za-z][\\w:-]*)/g,'$1<span style=\"color:#e06c75\">$2</span>');out=applyOutsideTags(out,/([A-Za-z_:][\\w:.-]*)(=)(&quot;.*?&quot;)/g,'<span style=\"color:#56b6c2\">$1</span>$2<span style=\"color:#98c379\">$3</span>');}"
            " if(ext==='.css'){out=applyOutsideTags(out,/(^[ \\t]*)([.#]?[A-Za-z_-][\\w:-]*)(\\s*\\{)/gm,'$1<span style=\"color:#e06c75\">$2</span>$3');out=applyOutsideTags(out,/([A-Za-z-]+)(\\s*:)/g,'<span style=\"color:#56b6c2\">$1</span>$2');}"
            " if(['.py','.js','.sh','.sql'].includes(ext)){out=applyOutsideTags(out,/(^[ \\t]*@[\\w.]+)/gm,'<span style=\"color:#e06c75\">$1</span>');}"
            " out=applyOutsideTags(out,/\\b(def|class|import|from|return|if|else|elif|for|while|try|except|with|as|yield|await|async|function|const|let|var|type|interface|enum|public|private|protected|static|readonly|do|switch|case|default|break|continue|new|delete|typeof|instanceof|void|this|super|in|of|null|undefined|true|false)\\b/g,'<span style=\"color:#c678dd\">$1</span>');"
            " out=applyOutsideTags(out,/\\b(str|int|float|bool|list|dict|tuple|set|None|self|cls|SELECT|FROM|WHERE|GROUP|ORDER|BY|JOIN|LEFT|RIGHT|INNER|OUTER|LIMIT|INSERT|UPDATE|DELETE|CREATE|TABLE|VALUES)\\b/g,'<span style=\"color:#e5c07b\">$1</span>');"
            " out=applyOutsideTags(out,/\\b(print|len|range|echo|printf|console|log)\\b/g,'<span style=\"color:#56b6c2\">$1</span>');"
            " out=applyOutsideTags(out,/\\b([A-Za-z_][\\w]*)(?=\\()/g,'<span style=\"color:#61afef\">$1</span>');"
            " out=applyOutsideTags(out,/([{}()[\\],.:;=+\\-/*<>])/g,'<span style=\"color:#7f848e\">$1</span>');"
            " return out;"
            "};"
            "const gutterRowHtml=(lineNumber)=>`<tr data-line=\"${lineNumber}\"><td class=\"ln\">${lineNumber}</td></tr>`;"
            "const codeRowHtml=(lineNumber,lineHtml)=>`<tr data-line=\"${lineNumber}\"><td class=\"lc\"><pre>${lineHtml||' '}</pre></td></tr>`;"
            "const appendLines=(chunkText,isFinal)=>{"
            " const fullText=(pending||'')+String(chunkText||'');"
            " const lines=fullText.split('\\n');"
            " if(!isFinal){pending=lines.pop()||'';}else{pending='';}"
            " if(lines.length){"
            "  const gutterRows=[];"
            "  const codeRows=[];"
            "  lines.forEach((line)=>{"
            "   const lineNumber=lineNo++;"
            "   gutterRows.push(gutterRowHtml(lineNumber));"
            "   codeRows.push(codeRowHtml(lineNumber,highlightText(line,fileExt)));"
            "  });"
            "  progressiveGutterBody.insertAdjacentHTML('beforeend',gutterRows.join(''));"
            "  progressiveCodeBody.insertAdjacentHTML('beforeend',codeRows.join(''));"
            " }"
            "};"
            "const maybeLoad=()=>{if(done||loading)return;if((progressiveScrollTarget.scrollTop+progressiveScrollTarget.clientHeight)>=(progressiveScrollTarget.scrollHeight-320)){void loadNext();}};"
            "let firstLoad=true;"
            "const loadNext=async()=>{"
            " if(done||loading)return;"
            " loading=true;"
            " const start=offset;"
            " const nextChunkBytes=firstLoad?Math.min(totalBytes,chunkBytes*4):Math.max(4096,Math.floor(chunkBytes/5));"
            " firstLoad=false;"
            " const end=Math.min(totalBytes-1,start+nextChunkBytes-1);"
            " setStatus(`Loading ${Math.min(totalBytes,end+1).toLocaleString()} / ${totalBytes.toLocaleString()} bytes...`);"
            " try{"
            "  const res=await fetch(rawUrl,{cache:'no-store',headers:{Range:`bytes=${start}-${end}`}});"
            "  if(!(res.ok||res.status===206)) throw new Error('preview failed');"
            "  const buf=await res.arrayBuffer();"
            "  if(buf.byteLength===0){done=true;setStatus(`Loaded ${offset.toLocaleString()} / ${totalBytes.toLocaleString()} bytes`);return;}"
            "  offset += buf.byteLength;"
            "  const finalChunk = offset >= totalBytes;"
            "  const textChunk=decoder.decode(buf,{stream:!finalChunk});"
            "  if(finalChunk){"
            "    const tail=decoder.decode();"
            "    appendLines(textChunk+tail,true);"
            "    done=true;"
            "    setStatus(`Loaded ${totalBytes.toLocaleString()} bytes`);"
            "  }else{"
            "    appendLines(textChunk,false);"
            "    setStatus(`Loaded ${offset.toLocaleString()} / ${totalBytes.toLocaleString()} bytes`);"
            "  }"
            " }catch(_){setStatus('Preview load failed.');}"
            " finally{loading=false;if(!done&&progressiveScrollTarget.scrollHeight<=progressiveScrollTarget.clientHeight+48){setTimeout(maybeLoad,0);}}"
            "};"
            "progressiveScrollTarget.addEventListener('scroll',maybeLoad,{passive:true});"
            "window.addEventListener('resize',maybeLoad,{passive:true});"
            "void loadNext();"
            "}"
        )
