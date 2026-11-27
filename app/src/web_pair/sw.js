self.addEventListener('push',event=>{const data=event.data?event.data.json():{};event.waitUntil(self.registration.showNotification(data.title||'ai_upper',{body:data.body,tag:data.tag}))})
